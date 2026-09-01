import os
import re
import pandas as pd
from urllib.parse import urlparse
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

PLATFORM_CONFIG = {

    "instagram": {
        "actor_id": "apify/instagram-scraper",
        "build_input": lambda urls: {
            "directUrls": urls, 
            "resultsType": "posts",
            "maxPostsPerProfile": 1,
            "maxRequestRetries": 1
        },
        "extract_meta": lambda item: item.get("ownerUsername") or item.get("ownerFullName") or "",
        "extract_text": lambda item: f"{item.get('caption') or item.get('text') or item.get('alt') or ''} | Post date: {item.get('timestamp', '')}".strip()    
    },

    "generic_web": {
        "actor_id": "apify/website-content-crawler",
        "build_input": lambda urls: {
            "startUrls": [{"url": u} for u in urls],
            "maxCrawlPages": len(urls),
            "maxCrawlingDepth": 0,
            "maxRequestRetries": 3,
            "crawlerType": "playwright:adaptive",
            "proxyConfiguration": {"useApifyProxy": True}
        },
        "extract_meta": lambda item: (item.get("metadata") or {}).get("title") or item.get("title") or "",
        "extract_text": lambda item: item.get("text") or item.get("markdown") or ""
    }
}


def categorize_url(url: str) -> str:
    if not isinstance(url, str) or not url.startswith("http"):
        return "invalid"
    domain = urlparse(url.lower()).netloc
    if "instagram.com" in domain:
        return "instagram"
    elif "facebook.com" in domain or "fb.com" in domain:
        return "generic_web"
    else:
        return "generic_web"

# Check if the input url, and the url scrab back is same or not, if same then return true, if not same then return false. 
def is_url_match(u_in: str, u_out: str) -> bool:
    if not u_in or not u_out:
        return False
    u_in_c = u_in.strip().rstrip('/').lower()
    u_out_c = u_out.strip().rstrip('/').lower()
    if u_in_c in u_out_c or u_out_c in u_in_c:
        return True
    ids_in = set(re.findall(r'\d{8,}', u_in_c))
    ids_out = set(re.findall(r'\d{8,}', u_out_c))
    if ids_in and ids_in.intersection(ids_out):
        return True
    return False

# Input: The DataFrame with variable Link_URL
# Output: The orginal DataFrame but two more variable of Content and Status
def run_apify_scraper(df_ppt: pd.DataFrame, progress_callback=None) -> pd.DataFrame:
    apify_token = os.getenv("APIFY_API_TOKEN")
    if not apify_token:
        raise ValueError("Apify Token could not be retrieved! Please ensure you have saved your settings in Step 2.")
    
    client = ApifyClient(token=apify_token)

    # if no Link_URL, then all the Status will be invalid
    if df_ppt.empty or 'Link_URL' not in df_ppt.columns:
        df_ppt['Content'] = ''
        df_ppt['Status'] = 'invalid'
        return df_ppt

    # Get the unique URL, catagorize by platform
    raw_url_list = df_ppt['Link_URL'].dropna().tolist()
    cleaned_urls = list(dict.fromkeys(
        u.strip().rstrip('/') for u in raw_url_list if isinstance(u, str) and u.strip()
    ))
    total_urls = len(cleaned_urls)
    if progress_callback:
        progress_callback(f"Starting Apify scraping task, processing {total_urls} unique links in total...")
    
    grouped_urls = {}
    for url in cleaned_urls:
        cat = categorize_url(url)
        grouped_urls.setdefault(cat, []).append(url)
        
    results_map = {}
    processed_count = 0

    # Loop each platform
    for platform, urls in grouped_urls.items():
        if platform == "invalid":
            for u in urls:
                results_map[u] = {"Content": "", "Status": "invalid"}
                processed_count += 1
                if progress_callback:
                    progress_callback(f"[{processed_count}/{total_urls}] Skipping invalid link...")
            continue

        if progress_callback:
            progress_callback(f"Processing {len(urls)} links for [{platform}] platform...")
        
        config = PLATFORM_CONFIG[platform]
        actor_input = config["build_input"](urls)
        
        try:
            run = client.actor(config["actor_id"]).call(run_input=actor_input)
            dataset_id = getattr(run, "default_dataset_id", None) or (run.get("defaultDatasetId") if isinstance(run, dict) else None)
            dataset_items = client.dataset(dataset_id).list_items().items if dataset_id else []

            # Loop each link in a platform
            for u in urls:
                processed_count += 1
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

                        if has_real_content and not is_useless_title:
                            status = "work"
                        else:
                            status = "expired"
                            
                        results_map[u] = {"Content": combined if status == "work" else "", "Status": status}
                        found = True
                        break 
                
                if not found:
                    results_map[u] = {"Content": "", "Status": "expired"}
                
                if progress_callback:
                    progress_callback(f"[{processed_count}/{total_urls}] 已抓取連結: {u} (狀態: {results_map[u]['Status']})")
                    
        except Exception as e:
            for u in urls:
                processed_count += 1
                results_map[u] = {"Content": "", "Status": "error"}
                if progress_callback:
                    progress_callback(f"[{processed_count}/{total_urls}] 錯誤: {u} ({e})")

    # From results_map, put the link and status to fill in the Input dataframe. 
    contents = []
    statuses = []
    for u in df_ppt['Link_URL']:
        u_clean = str(u).strip().rstrip('/') if pd.notnull(u) else ""
        data = results_map.get(u_clean, {"Content": "", "Status": "error"})
        contents.append(data["Content"])
        statuses.append(data["Status"])

    df_ppt['Content'] = contents
    df_ppt['Status'] = statuses
    if progress_callback:
        progress_callback(f"Scraping and data consolidation completed!")
    return df_ppt