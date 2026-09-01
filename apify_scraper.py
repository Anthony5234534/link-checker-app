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
