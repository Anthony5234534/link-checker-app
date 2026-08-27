"""
highlight_ppt.py

Reads the AI/link-checking report (final_checked_report.xlsx) together with
the ORIGINAL PowerPoint file, and produces a copy of the PowerPoint with
each hyperlink (and each "[Link]" missing-link placeholder) highlighted in
color according to its Status/Result:

    - Status == 'work' AND Result == 'match'  -> GREEN  (confirmed good link)
    - anything else (mismatch / error / expired / invalid / no content)
                                               -> LIGHT RED (needs attention)

Matching strategy
------------------
Excel rows are matched back to PPT content by re-running the EXACT SAME
traversal order as the original ppt_extractor.py (same slide -> shape ->
paragraph -> run walk, same "[Link]" placeholder regex). For each slide,
Excel rows for that slide are consumed strictly in order as matching
"events" (a real hyperlink run, or a literal "[Link]" text placeholder)
are encountered in the PPT.

This is necessary -- NOT optional -- because the same URL can appear
multiple times across the deck with DIFFERENT AI match results depending
on which sentence it supports, so a simple "look up by URL" approach would
silently apply the wrong color to some occurrences. Order-based, per-slide
matching is the only approach that is guaranteed correct.

Usage:
    python highlight_ppt.py input.pptx final_checked_report.xlsx output.pptx
"""

import re
import copy
import sys
from collections import defaultdict

import pandas as pd
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

# ----------------------------------------------------------------------
# Highlight colors (OOXML <a:highlight> uses plain RGB hex, not limited to
# the standard Office highlighter palette)
# ----------------------------------------------------------------------

GREEN_HIGHLIGHT = "92D050"   # confirmed good link (work + match)
YELLOW_HIGHLIGHT = "FFFF00"  # broken link (error / expired / invalid)
RED_HIGHLIGHT = "FF0000"     # link works but content does not match (work + mismatch)

MISSING_LINK_PATTERN = re.compile(r'\[\s*link\s*\]', flags=re.IGNORECASE)


# ----------------------------------------------------------------------
# Color decision logic
# ----------------------------------------------------------------------

def get_highlight_color(status, result):
    """
    Decides the highlight color for a single Excel row:
      - status == 'work' and result == 'match'    -> green  (confirmed good)
      - status == 'work' and result == 'mismatch' -> red    (reachable, but content doesn't match)
      - status in {'error', 'expired', 'invalid'} -> yellow (broken / unreachable link)
    """
    status = str(status).strip().lower()
    result = str(result).strip().lower()

    if status == "work" and result == "match":
        return GREEN_HIGHLIGHT
    if status == "work" and result == "mismatch":
        return RED_HIGHLIGHT
    return YELLOW_HIGHLIGHT


# ----------------------------------------------------------------------
# Low-level OOXML helpers (python-pptx has no built-in "text highlight"
# API, so we manipulate the <a:rPr><a:highlight> element directly)
# ----------------------------------------------------------------------

def _get_or_add_rPr(r_xml):
    """Gets (or creates, as the first child, per OOXML schema order) the
    <a:rPr> element of a raw <a:r> run XML element."""
    rPr = r_xml.find(qn('a:rPr'))
    if rPr is None:
        rPr = r_xml.makeelement(qn('a:rPr'), {})
        r_xml.insert(0, rPr)
    return rPr


def _get_or_add_t(r_xml):
    """Gets (or creates) the <a:t> text element of a raw <a:r> run XML element."""
    t = r_xml.find(qn('a:t'))
    if t is None:
        t = r_xml.makeelement(qn('a:t'), {})
        r_xml.append(t)
    return t


# The CT_TextCharacterProperties (<a:rPr>) schema requires its children to
# appear in this exact order. Since these runs are hyperlinks, their <a:rPr>
# already contains <a:hlinkClick>; simply appending <a:highlight> at the end
# would place it AFTER hlinkClick, which violates the schema. Real
# PowerPoint enforces this ordering strictly and silently drops
# out-of-sequence elements on open -- LibreOffice is lenient about it and
# renders it anyway, which is why the highlight was invisible only in real
# PowerPoint. We insert <a:highlight> at the correct schema position instead
# of blindly appending it.
_RPR_CHILD_ORDER = [
    'a:ln', 'a:noFill', 'a:solidFill', 'a:gradFill', 'a:blipFill', 'a:pattFill', 'a:grpFill',
    'a:effectLst', 'a:effectDag',
    'a:highlight',
    'a:uLnTx', 'a:uLn', 'a:uFillTx', 'a:uFill',
    'a:latin', 'a:ea', 'a:cs', 'a:sym',
    'a:hlinkClick', 'a:hlinkMouseOver', 'a:rtl', 'a:extLst',
]


def _insert_in_schema_order(parent, new_child, tag):
    """Inserts new_child into parent at the position required by
    _RPR_CHILD_ORDER, based on the tags of parent's existing children."""
    target_index = _RPR_CHILD_ORDER.index(tag)
    for existing in parent:
        existing_tag = qn_to_short(existing.tag)
        if existing_tag in _RPR_CHILD_ORDER and _RPR_CHILD_ORDER.index(existing_tag) > target_index:
            existing.addprevious(new_child)
            return
    parent.append(new_child)


def qn_to_short(fq_tag):
    """Converts a fully-qualified lxml tag (e.g. '{...}hlinkClick') back to
    the short 'a:hlinkClick' form used in _RPR_CHILD_ORDER."""
    return 'a:' + fq_tag.split('}')[-1]


def apply_highlight(r_xml, rgb_hex):
    """Applies (or replaces) a text highlight color on a raw <a:r> run XML
    element, inserting it at the schema-correct position within <a:rPr>."""
    rPr = _get_or_add_rPr(r_xml)
    existing = rPr.find(qn('a:highlight'))
    if existing is not None:
        rPr.remove(existing)
    highlight_el = rPr.makeelement(qn('a:highlight'), {})
    srgb_el = highlight_el.makeelement(qn('a:srgbClr'), {'val': rgb_hex})
    highlight_el.append(srgb_el)
    _insert_in_schema_order(rPr, highlight_el, 'a:highlight')


def clone_run_with_text(run, new_text):
    """Deep-copies a run's XML (preserving all formatting) with different
    text content. Returns the new, not-yet-inserted <a:r> element."""
    new_r = copy.deepcopy(run._r)
    _get_or_add_t(new_r).text = new_text
    return new_r


def split_run_and_highlight(run, local_start, local_end, rgb_hex):
    """
    Splits a run's text into [before, matched, after] and inserts up to two
    new sibling runs (matched, after) right after the original run (which
    is mutated in place to hold only the "before" portion). Only the
    "matched" segment gets the highlight -- formatting is otherwise
    identical across all three pieces, since they're clones of the
    original run.
    """
    text = run.text
    before = text[:local_start]
    matched = text[local_start:local_end]
    after = text[local_end:]

    _get_or_add_t(run._r).text = before

    insert_after = run._r
    if matched:
        matched_r = clone_run_with_text(run, matched)
        apply_highlight(matched_r, rgb_hex)
        insert_after.addnext(matched_r)
        insert_after = matched_r
    if after:
        after_r = clone_run_with_text(run, after)
        insert_after.addnext(after_r)


def iter_shapes(shapes):
    """Recursively yields all shapes, including those nested inside groups
    (mirrors the original ppt_extractor.py exactly)."""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(shape.shapes)
        else:
            yield shape


# ----------------------------------------------------------------------
# Per-slide row queues (order-based matching)
# ----------------------------------------------------------------------

def build_slide_queues(df: pd.DataFrame):
    """Groups Excel rows by 'Slide number', preserving their original
    (top-to-bottom) row order, and returns {slide_num: [row_dict, ...]}."""
    queues = defaultdict(list)
    for _, row in df.iterrows():
        queues[int(row["Slide number"])].append(row.to_dict())
    return queues


def pop_next_row(queue, slide_num, context_label):
    """Pops the next row for this slide's queue, or returns None with a
    warning if the PPT and Excel have gone out of sync (e.g. the PPT was
    edited after the report was generated)."""
    if not queue:
        print(f"WARNING: slide {slide_num} -- ran out of matching Excel rows "
              f"while processing '{context_label}'. The PPT may have been "
              f"edited after the report was generated; skipping this item.")
        return None
    return queue.pop(0)


# ----------------------------------------------------------------------
# Missing-link ("[Link]" typed as plain text) handling
# ----------------------------------------------------------------------

def handle_missing_link_matches(buffer_text, run_offsets, slide_queue, slide_num):
    """
    Finds every literal "[Link]"-style placeholder in the accumulated
    non-hyperlink text of a paragraph (buffer_text), consumes the matching
    Excel row (should be a MISSING_URL_MANUAL_REQUIRED row) for each one in
    order, and highlights the exact matched text span in the PPT.
    """
    matches = list(MISSING_LINK_PATTERN.finditer(buffer_text))
    for match in matches:
        row = pop_next_row(slide_queue, slide_num, "missing-link placeholder")
        if row is None:
            continue
        color = get_highlight_color(row.get("Status"), row.get("Result"))
        _highlight_span(match.start(), match.end(), run_offsets, color, slide_num)


def _highlight_span(m_start, m_end, run_offsets, color, slide_num):
    """Maps a [m_start, m_end) character range in the accumulated buffer
    back to the actual run(s) that contain it, and highlights it."""
    overlapping = [(run, start, end) for (run, start, end) in run_offsets
                   if end > m_start and start < m_end]

    if len(overlapping) == 1:
        run, start, _ = overlapping[0]
        split_run_and_highlight(run, m_start - start, m_end - start, color)
    elif len(overlapping) > 1:
        # Rare: the "[Link]" text happens to be split across a run
        # boundary (e.g. different formatting mid-phrase). Fall back to
        # highlighting every overlapping run in full rather than crashing.
        print(f"WARNING: slide {slide_num} -- a missing-link match spans "
              f"multiple runs; highlighting each overlapping run in full "
              f"as a fallback (highlight may extend slightly beyond '[Link]').")
        for run, _, _ in overlapping:
            apply_highlight(run._r, color)
    else:
        print(f"WARNING: slide {slide_num} -- could not locate the run(s) "
              f"for a missing-link match; skipped.")


# ----------------------------------------------------------------------
# Main traversal (mirrors ppt_extractor.py's parse_ppt_to_excel exactly,
# but highlights instead of recording rows)
# ----------------------------------------------------------------------

def highlight_presentation(pptx_path, excel_path, output_path):
    print(f"Reading report: {excel_path} ...")
    df = pd.read_excel(excel_path)
    slide_queues = build_slide_queues(df)

    print(f"Reading presentation: {pptx_path} ...")
    prs = Presentation(pptx_path)

    total_highlighted = 0

    for slide_index, slide in enumerate(prs.slides):
        slide_num = slide_index + 1
        queue = slide_queues.get(slide_num, [])
        if not queue:
            continue  # this slide had no links in the report

        for shape in iter_shapes(slide.shapes):
            if not shape.has_text_frame:
                continue

            for paragraph in shape.text_frame.paragraphs:
                current_preceding = ""
                current_preceding_runs = []  # [(run, start_offset, end_offset), ...]
                offset = 0

                for run in paragraph.runs:
                    text_content = run.text
                    link_url = run.hyperlink.address if run.hyperlink else None

                    if link_url:
                        # 1. Resolve any missing-link placeholders that
                        #    appeared before this real hyperlink.
                        handle_missing_link_matches(
                            current_preceding, current_preceding_runs, queue, slide_num
                        )

                        # 2. Resolve the real hyperlink run itself.
                        row = pop_next_row(queue, slide_num, f"hyperlink ({link_url})")
                        if row is not None:
                            color = get_highlight_color(row.get("Status"), row.get("Result"))
                            apply_highlight(run._r, color)
                            total_highlighted += 1

                        # 3. Reset the accumulator for the next segment.
                        current_preceding = ""
                        current_preceding_runs = []
                        offset = 0
                    else:
                        start = offset
                        end = offset + len(text_content)
                        current_preceding_runs.append((run, start, end))
                        current_preceding += text_content
                        offset = end

                # End of paragraph: handle any trailing missing-link
                # placeholders that weren't followed by a real hyperlink.
                handle_missing_link_matches(
                    current_preceding, current_preceding_runs, queue, slide_num
                )

        if queue:
            print(f"WARNING: slide {slide_num} -- {len(queue)} Excel row(s) "
                  f"were not consumed (more report rows than links found on "
                  f"this slide). The PPT may not exactly match this report.")

    prs.save(output_path)
    print(f"Done. {total_highlighted} hyperlink(s) highlighted. Saved to: {output_path}")
    return output_path
