import os
import re
import pandas as pd
from urllib.parse import urlparse
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")

if not APIFY_TOKEN:
    raise ValueError("找不到 Apify Token！請確認 .env 檔案中是否已設定 APIFY_API_TOKEN。")

client = ApifyClient(token=APIFY_TOKEN)

PLATFORM_CONFIG = {
    "instagram": {
        "actor_id": "apify/instagram-scraper",
        "build_input": lambda urls: {
            "directUrls": urls, 
            "resultsType": "details",
            "maxRequestRetries": 1
        },
        "extract_meta": lambda item: item.get("ownerUsername") or item.get("ownerFullName") or "",
        "extract_text": lambda item: item.get("caption") or item.get("text") or item.get("alt") or ""
    },
    "facebook": {
        "actor_id": "apify/facebook-posts-scraper",
        "build_input": lambda urls: {
            "startUrls": [{"url": u} for u in urls],
            "maxRequestRetries": 3,
            "proxyConfiguration": {"useApifyProxy": True}
        },
        "extract_meta": lambda item: (item.get("user") or {}).get("name", "") if isinstance(item.get("user"), dict) else "",
        "extract_text": lambda item: item.get("text", "")
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
        return "facebook"
    else:
        return "generic_web"

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

def run_apify_scraper(df_ppt: pd.DataFrame) -> pd.DataFrame:
    """
    接收 PPT 解析後的 DataFrame，自動提取裡面的 Link_URL 進行爬取，
    並將結果與原本的 DataFrame 進行整合，回傳包含 Content 與 Status 的完整 DataFrame。
    """
    if df_ppt.empty or 'Link_URL' not in df_ppt.columns:
        df_ppt['Content'] = ''
        df_ppt['Status'] = 'invalid'
        return df_ppt

    url_list = df_ppt['Link_URL'].dropna().unique().tolist()
    print(f"🚀 開始 Apify 爬蟲任務，共計處理 {len(url_list)} 個不重複連結...")
    
    cleaned_urls = [u.strip().rstrip('/') for u in url_list if isinstance(u, str) and u.strip()]
    
    grouped_urls = {}
    for url in cleaned_urls:
        cat = categorize_url(url)
        grouped_urls.setdefault(cat, []).append(url)
        
    results_map = {}

    for platform, urls in grouped_urls.items():
        if platform == "invalid":
            for u in urls:
                results_map[u] = {"Content": "", "Status": "invalid"}
            continue

        print(f"📦 正在處理 [{platform}] 平台的 {len(urls)} 個連結...")
        config = PLATFORM_CONFIG[platform]
        actor_input = config["build_input"](urls)
        
        try:
            run = client.actor(config["actor_id"]).call(run_input=actor_input)
            dataset_id = getattr(run, "default_dataset_id", None) or (run.get("defaultDatasetId") if isinstance(run, dict) else None)
            dataset_items = client.dataset(dataset_id).list_items().items if dataset_id else []
            
            for u in urls:
                found = False
                for item in dataset_items:
                    retrieved_url = item.get("inputUrl") or item.get("directUrl") or item.get("url") or ""
                    if is_url_match(u, retrieved_url):
                        meta = config["extract_meta"](item)
                        text = config["extract_text"](item)
                        
                        meta_str = str(meta) if meta else ""
                        text_str = str(text) if text else ""
                        combined = f"[{meta_str}] {text_str}".strip() if meta_str else text_str.strip()
                        
                        invalid_keywords = ["facebook", "login", "log in", "[微博] 微博", "登录", "提示"]
                        is_useless_title = any(kw in combined.lower() for kw in invalid_keywords) and len(combined) < 30
                        
                        if combined and not is_useless_title and combined != "None":
                            status = "work"
                        else:
                            status = "expired"
                            
                        results_map[u] = {"Content": combined if status == "work" else "", "Status": status}
                        found = True
                        break 
                
                if not found:
                    results_map[u] = {"Content": "", "Status": "expired"}
                    
        except Exception as e:
            print(f"❌ 執行 [{platform}] 爬蟲時發生錯誤: {e}")
            for u in urls:
                results_map[u] = {"Content": "", "Status": "error"}

    # 將爬蟲結果對應回原本的 DataFrame (支援同一個網址在不同頁數重複出現的情況)
    contents = []
    statuses = []
    for u in df_ppt['Link_URL']:
        u_clean = str(u).strip().rstrip('/') if pd.notnull(u) else ""
        data = results_map.get(u_clean, {"Content": "", "Status": "error"})
        contents.append(data["Content"])
        statuses.append(data["Status"])

    df_ppt['Content'] = contents
    df_ppt['Status'] = statuses
    print(f"✅ 爬蟲與資料整併完成！")
    return df_ppt

