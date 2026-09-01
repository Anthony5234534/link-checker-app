import os
import time
import pandas as pd
import streamlit as st
from apify_client import ApifyClient

from apify_scraper import PLATFORM_CONFIG, categorize_url, is_url_match

# ------------------------------------------------------------------
# Tunable settings
# ------------------------------------------------------------------
# Max number of URLs sent to Apify in a single actor call, per platform.
# Instagram scraping in particular is prone to rate limiting / temporary
# blocking when too many direct URLs are requested in one batch, which can
# cause an entire actor run to fail or return zero items EVEN THOUGH the
# run itself finishes without raising a Python exception. Splitting into
# smaller batches reduces how much work is lost if one batch gets blocked,
# and makes automatic retries much cheaper.
INSTAGRAM_BATCH_SIZE = 50
GENERIC_WEB_BATCH_SIZE = 80

# If a batch looks like it failed (see _scrape_batch), retry it this many
# times before giving up and marking the links as "error".
MAX_BATCH_RETRIES = 2
RETRY_BACKOFF_SECONDS = 5

# Small pause between consecutive batches of the same platform, to reduce
# the chance of triggering rate limiting from sending requests back-to-back.
INTER_BATCH_PAUSE_SECONDS = 2


@st.cache_resource
def get_step3_registry():
    """
    A single dict shared across all Streamlit reruns and sessions within this
    app process (via st.cache_resource), used to track the background
    scraping thread + progress for each session id (sid).
    """
    return {}


def _batch_size_for(platform: str) -> int:
    if platform == "instagram":
        return INSTAGRAM_BATCH_SIZE
    return GENERIC_WEB_BATCH_SIZE


def _scrape_batch(client: ApifyClient, platform: str, urls: list, progress_callback=None):
    """
    Scrape a single batch of URLs belonging to the same platform.

    Returns (results, ok):
      results -> dict mapping url -> {"Content": str, "Status": str}
      ok      -> False if the Apify run did not finish with status SUCCEEDED,
                 or if it returned zero dataset items despite being sent a
                 non-empty batch of URLs. Zero items for a whole batch is a
                 strong signal that something went wrong on the scraping
                 side (rate limiting, temporary IP block, actor error) rather
                 than every single link in the batch genuinely having no
                 content. When ok is False, all links in the batch are
                 marked "error" so the caller can retry them.
    """
    results = {}
    config = PLATFORM_CONFIG[platform]
    actor_input = config["build_input"](urls)

    try:
        run = client.actor(config["actor_id"]).call(run_input=actor_input)

        run_status = getattr(run, "status", None)
        if run_status is None and isinstance(run, dict):
            run_status = run.get("status")

        dataset_id = getattr(run, "default_dataset_id", None) or (run.get("defaultDatasetId") if isinstance(run, dict) else None)
        dataset_items = client.dataset(dataset_id).list_items().items if dataset_id else []

        if progress_callback:
            progress_callback(
                f"[{platform}] Apify run status: {run_status}, batch size: {len(urls)}, items returned: {len(dataset_items)}"
            )

        run_looks_failed = run_status not in (None, "SUCCEEDED")
        run_looks_empty = len(urls) > 0 and len(dataset_items) == 0

        if run_looks_failed or run_looks_empty:
            for u in urls:
                results[u] = {"Content": "", "Status": "error"}
            return results, False

        for u in urls:
            found = False
            for item in dataset_items:
                retrieved_url = item.get("inputUrl") or item.get("directUrl") or item.get("url") or ""
                if is_url_match(u, retrieved_url):
                    meta = config["extract_meta"](item)
                    text = config["extract_text"](item)
                    meta_str = str(meta) if meta else ""
                    text_str = str(text) if text else ""

                    if platform == "instagram":
                        combined = f"Author: {meta_str} | Post content: {text_str}".strip()
                    else:
                        combined = f"[{meta_str}] {text_str}".strip() if meta_str else text_str.strip()

                    invalid_keywords = ["login", "log in", "登录", "提示", "無法使用"]
                    is_useless_title = any(kw in combined.lower() for kw in invalid_keywords) and len(combined) < 30

                    has_real_content = False
                    if platform == "instagram":
                        has_caption = bool(item.get('caption') or item.get('text') or item.get('alt'))
                        has_timestamp = bool(item.get('timestamp'))
                        if meta or has_caption or has_timestamp:
                            has_real_content = True
                    else:
                        has_real_content = bool(meta_str.strip() or text_str.strip())
                        if "explore the things you love" in text_str.lower():
                            has_real_content = False

                    status = "work" if (has_real_content and not is_useless_title) else "expired"
                    results[u] = {"Content": combined if status == "work" else "", "Status": status}
                    found = True
                    break

            if not found:
                results[u] = {"Content": "", "Status": "expired"}

            if progress_callback:
                progress_callback(f"Fetched link: {u} (status: {results[u]['Status']})")

        return results, True

    except Exception as e:
        for u in urls:
            results[u] = {"Content": "", "Status": "error"}
        if progress_callback:
            progress_callback(f"Error while scraping batch for platform [{platform}]: {e}")
        return results, False


def _count_resolved(results_map: dict) -> int:
    """Links that have a final, trustworthy status (not a failed batch)."""
    return sum(1 for v in results_map.values() if v.get("Status") != "error")


def count_resolved_from_checkpoint(checkpoint_path: str) -> int:
    """
    Helper for the UI: read the checkpoint file on disk and count how many
    unique links have a resolved (non-error) status, without needing a live
    job object. Used to render progress even after an app restart.
    """
    if not os.path.exists(checkpoint_path):
        return 0
    try:
        df_checkpoint = pd.read_excel(checkpoint_path)
        if "Status" not in df_checkpoint.columns:
            return 0
        return int((df_checkpoint["Status"] != "error").sum())
    except Exception:
        return 0


def _load_checkpoint_results_map(checkpoint_path: str) -> dict:
    results_map = {}
    if os.path.exists(checkpoint_path):
        df_checkpoint = pd.read_excel(checkpoint_path)
        for _, row in df_checkpoint.iterrows():
            results_map[row["Link_URL"]] = {
                "Content": row.get("Content", "") if pd.notnull(row.get("Content", "")) else "",
                "Status": row.get("Status", "")
            }
    return results_map


def _save_checkpoint(checkpoint_path: str, results_map: dict):
    df_checkpoint = pd.DataFrame([
        {"Link_URL": u, "Content": v["Content"], "Status": v["Status"]}
        for u, v in results_map.items()
    ])
    df_checkpoint.to_excel(checkpoint_path, index=False)


def _step3_worker(sid, input_file_path, output_path, checkpoint_path, job):
    """
    Background worker for Step 3.

    Splits all unique links into small per-platform batches and scrapes them
    one batch at a time (instead of sending hundreds of links to Apify in a
    single call). After every batch:
      - The full accumulated results are written to checkpoint_path, so
        progress survives disconnects and can be resumed later.
      - Links from a batch that looks like it failed (see _scrape_batch) are
        marked "error" instead of "expired", and will be automatically
        retried the next time this worker runs (including on manual resume),
        instead of being permanently and silently treated as having no
        content.
    """
    try:
        df_ppt = pd.read_excel(input_file_path)

        if df_ppt.empty or "Link_URL" not in df_ppt.columns:
            df_ppt["Content"] = ""
            df_ppt["Status"] = "invalid"
            df_ppt.to_excel(output_path, index=False)
            with job["lock"]:
                job["finished"] = True
                job["done"] = 0
                job["total"] = 0
            return

        apify_token = os.getenv("APIFY_API_TOKEN")
        if not apify_token:
            raise ValueError("Apify Token could not be retrieved! Please ensure you have saved your settings in Step 2.")
        client = ApifyClient(token=apify_token)

        url_list = df_ppt["Link_URL"].dropna().unique().tolist()
        cleaned_urls = [u.strip().rstrip("/") for u in url_list if isinstance(u, str) and u.strip()]

        grouped_urls = {}
        for url in cleaned_urls:
            cat = categorize_url(url)
            grouped_urls.setdefault(cat, []).append(url)

        total_unique = len(cleaned_urls)

        # Load existing checkpoint. Links marked "error" are treated as NOT
        # done yet, so they get automatically retried on resume.
        results_map = _load_checkpoint_results_map(checkpoint_path)

        with job["lock"]:
            job["total"] = total_unique
            job["done"] = _count_resolved(results_map)

        def batch_cb(message, is_detail=False):
            with job["lock"]:
                job["logs"].append(message)
                job["logs"] = job["logs"][-30:]

        for platform, urls in grouped_urls.items():

            if platform == "invalid":
                for u in urls:
                    if u not in results_map or results_map[u].get("Status") == "error":
                        results_map[u] = {"Content": "", "Status": "invalid"}
                _save_checkpoint(checkpoint_path, results_map)
                with job["lock"]:
                    job["done"] = _count_resolved(results_map)
                    job["last_update"] = time.time()
                continue

            # Links still needing work: never scraped before, OR previously
            # failed with "error" (worth retrying).
            remaining_urls = [
                u for u in urls
                if u not in results_map or results_map[u].get("Status") == "error"
            ]
            if not remaining_urls:
                continue

            batch_size = _batch_size_for(platform)

            for i in range(0, len(remaining_urls), batch_size):
                batch = remaining_urls[i:i + batch_size]
                batch_cb(f"Scraping [{platform}] batch: {len(batch)} links (batch size limit: {batch_size})...")

                batch_results = None
                for attempt in range(1, MAX_BATCH_RETRIES + 2):  # 1 initial try + retries
                    batch_results, ok = _scrape_batch(client, platform, batch, progress_callback=batch_cb)
                    if ok:
                        break
                    if attempt <= MAX_BATCH_RETRIES:
                        batch_cb(
                            f"[{platform}] Batch attempt {attempt} looked unsuccessful "
                            f"(possible rate limiting / temporary block) — retrying in {RETRY_BACKOFF_SECONDS}s..."
                        )
                        time.sleep(RETRY_BACKOFF_SECONDS)
                    else:
                        batch_cb(
                            f"[{platform}] Batch failed after {MAX_BATCH_RETRIES} retries — "
                            f"marked as 'error', will retry automatically next time you resume."
                        )

                results_map.update(batch_results)
                _save_checkpoint(checkpoint_path, results_map)

                with job["lock"]:
                    job["done"] = _count_resolved(results_map)
                    job["last_update"] = time.time()

                if i + batch_size < len(remaining_urls):
                    time.sleep(INTER_BATCH_PAUSE_SECONDS)

        # All unique links processed - assemble the final dataframe in original row order.
        # Note: if any links are still marked "error" after all retries, they will still
        # appear in the final file (as "error") so nothing silently disappears; re-running
        # Step 3 later (same input) will retry only those links.
        contents = []
        statuses = []
        for u in df_ppt["Link_URL"]:
            u_clean = str(u).strip().rstrip("/") if pd.notnull(u) else ""
            data = results_map.get(u_clean, {"Content": "", "Status": "error"})
            contents.append(data["Content"])
            statuses.append(data["Status"])

        df_final = df_ppt.copy()
        df_final["Content"] = contents
        df_final["Status"] = statuses
        df_final.to_excel(output_path, index=False)

        with job["lock"]:
            job["finished"] = True
            job["error"] = None

    except Exception as e:
        with job["lock"]:
            job["error"] = str(e)
            job["finished"] = True
