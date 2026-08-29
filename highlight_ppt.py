import re
import copy
from collections import defaultdict
from ppt_parser import iter_ppt_links

import pandas as pd
from pptx import Presentation
from pptx.oxml.ns import qn


# Highlight colors 
GREEN_HIGHLIGHT = "92D050"   # confirmed good link (work + match)
YELLOW_HIGHLIGHT = "FFFF00"  # broken link (error / expired / invalid)
RED_HIGHLIGHT = "FF0000"     # link works but content does not match (work + mismatch)

MISSING_LINK_PATTERN = re.compile(r'\[\s*link\s*\]', flags=re.IGNORECASE)

# Color decision logic
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
# Custom PowerPoint Highlight Package 

def _get_or_add_rPr(r_xml):
    rPr = r_xml.find(qn('a:rPr'))
    if rPr is None:
        rPr = r_xml.makeelement(qn('a:rPr'), {})
        r_xml.insert(0, rPr)
    return rPr

def _get_or_add_t(r_xml):
    t = r_xml.find(qn('a:t'))
    if t is None:
        t = r_xml.makeelement(qn('a:t'), {})
        r_xml.append(t)
    return t

_RPR_CHILD_ORDER = [
    'a:ln', 'a:noFill', 'a:solidFill', 'a:gradFill', 'a:blipFill', 'a:pattFill', 'a:grpFill',
    'a:effectLst', 'a:effectDag',
    'a:highlight',
    'a:uLnTx', 'a:uLn', 'a:uFillTx', 'a:uFill',
    'a:latin', 'a:ea', 'a:cs', 'a:sym',
    'a:hlinkClick', 'a:hlinkMouseOver', 'a:rtl', 'a:extLst',
]

def _insert_in_schema_order(parent, new_child, tag):
    target_index = _RPR_CHILD_ORDER.index(tag)
    for existing in parent:
        existing_tag = qn_to_short(existing.tag)
        if existing_tag in _RPR_CHILD_ORDER and _RPR_CHILD_ORDER.index(existing_tag) > target_index:
            existing.addprevious(new_child)
            return
    parent.append(new_child)

def qn_to_short(fq_tag):
    return 'a:' + fq_tag.split('}')[-1]

def apply_highlight(r_xml, rgb_hex):
    rPr = _get_or_add_rPr(r_xml)
    existing = rPr.find(qn('a:highlight'))
    if existing is not None:
        rPr.remove(existing)
    highlight_el = rPr.makeelement(qn('a:highlight'), {})
    srgb_el = highlight_el.makeelement(qn('a:srgbClr'), {'val': rgb_hex})
    highlight_el.append(srgb_el)
    _insert_in_schema_order(rPr, highlight_el, 'a:highlight')

def clone_run_with_text(run, new_text):
    new_r = copy.deepcopy(run._r)
    _get_or_add_t(new_r).text = new_text
    return new_r

def split_run_and_highlight(run, local_start, local_end, rgb_hex):
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

# ----------------------------------------------------------------------



# ----------------------------------------------------------------------
# for each slide, if number of link in input ppt is larger than that of input report excel. 

def build_slide_queues(df: pd.DataFrame):
    queues = defaultdict(list)
    for _, row in df.iterrows():
        queues[int(row["Slide number"])].append(row.to_dict())
    return queues

def pop_next_row(queue, slide_num, context_label):
    if not queue:
        raise ValueError(
            f"\n[Safeguard Triggered] Slide {slide_num} Misalignment Detected!\n"
            f"While trying to highlight '{context_label}', the Excel report data for this slide has run out.\n"
            f"Critical Warning: You may have uploaded the wrong PPT or Excel file, or the PPT was modified after the report was generated. Execution has been aborted; no output file was saved."
        )
    return queue.pop(0)

# ----------------------------------------------------------------------


# Missing-link ("[Link]" typed as plain text) handling

def handle_missing_link_matches(buffer_text, run_offsets, slide_queue, slide_num):
    matches = list(MISSING_LINK_PATTERN.finditer(buffer_text))
    for match in matches:
        row = pop_next_row(slide_queue, slide_num, "missing-link placeholder")
        color = get_highlight_color(row.get("Status"), row.get("Result"))
        _highlight_span(match.start(), match.end(), run_offsets, color, slide_num)

def _highlight_span(m_start, m_end, run_offsets, color, slide_num):
    overlapping = [(run, start, end) for (run, start, end) in run_offsets
                   if end > m_start and start < m_end]

    if len(overlapping) == 1:
        run, start, _ = overlapping[0]
        split_run_and_highlight(run, m_start - start, m_end - start, color)
    elif len(overlapping) > 1:
        for run, _, _ in overlapping:
            apply_highlight(run._r, color)

# ----------------------------------------------------------------------

# Main function
# Input: pptx_path, excel_path, output_path (ppt and the excel report)
# Output: output_path (highlighted ppt)

def highlight_presentation(pptx_path, excel_path, output_path):
    print(f"Reading report: {excel_path} ...")
    df = pd.read_excel(excel_path)
    slide_queues = build_slide_queues(df)

    print(f"Reading presentation: {pptx_path} ...")
    prs = Presentation(pptx_path)

    total_highlighted = 0

    for item in iter_ppt_links(prs):
        slide_num = item['slide_num']
        queue = slide_queues.get(slide_num, [])
        url = item['url']
        item_type = item['type']

        if item_type == 'table_horizontal':
            context = f"table horizontal link ({url})"
        elif item_type == 'table_vertical':
            context = f"table vertical link ({url})"
        elif item_type == 'single_link':
            context = f"single hyperlink ({url})"
        elif item_type == 'hyperlink':
            context = f"hyperlink ({url})"
        elif item_type == 'missing_link':
            context = "missing-link placeholder"
        else:
            continue

        row_excel = pop_next_row(queue, slide_num, context)
        color = get_highlight_color(row_excel.get("Status"), row_excel.get("Result"))
        
        if item_type == 'missing_link':
            _highlight_span(item['match_start'], item['match_end'], item['run_offsets'], color, slide_num)
        else:
            apply_highlight(item['run']._r, color)
            
        total_highlighted += 1

    # for each slide, if number of link in excel is larger then that in ppt, 
    for slide_num, queue in slide_queues.items():
        if queue: 
            raise ValueError(
                f"\n[Safeguard Triggered] Slide {slide_num} Misalignment Detected!\n"
                f"After processing this slide, there are still {len(queue)} unused rows left in the Excel report queue.\n"
                f"Critical Warning: You may have uploaded the wrong PPT or Excel file, or the PPT was modified after the report was generated. Execution has been aborted; no output file was saved."
            )

    prs.save(output_path)
    print(f"Done. {total_highlighted} hyperlink(s) highlighted. Saved to: {output_path}")
    return output_path