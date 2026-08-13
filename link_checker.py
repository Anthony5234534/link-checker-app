import os
import sys
import time
import random
import pandas as pd
import requests

def check_url_status(url):
    if pd.isna(url) or not isinstance(url, str) or not url.startswith("http"):
        return "invalid"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    }

    try:
        time.sleep(random.uniform(1.0, 3.0))
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        
        if response.status_code == 404 or response.status_code == 410:
            return "expired"
        
        if response.status_code >= 500:
            return "invalid"
            
        final_url = response.url.lower()
        if "[instagram.com/accounts/login](https://instagram.com/accounts/login)" in final_url or "[facebook.com/login](https://facebook.com/login)" in final_url:
            return "expired"

        html_content = response.text.lower()
        expired_keywords = [
            "抱歉，此頁面無法使用", 
            "sorry, this page isn't available", 
            "頁面不存在", 
            "已移除", 
            "此內容目前無法使用",
            "this content isn't available right now",
            "page not found"
        ]
        
        for keyword in expired_keywords:
            if keyword in html_content:
                return "expired"
        
        return "work"

    except requests.exceptions.RequestException:
        return "invalid"

def run_link_checker(input_file="Ai_checked.xlsx", output_file="final_output.xlsx", progress_callback=None):
    """
    Checks URL status and adds 'progress_callback' for Streamlit integration.
    """
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
        
    df = pd.read_excel(input_file)
    
    url_col = "Link_URL" if "Link_URL" in df.columns else "URL" if "URL" in df.columns else None
    if not url_col:
        raise ValueError("Error: Cannot find 'Link_URL' or 'URL' column in the Excel file.")
            
    statuses = []
    total_rows = len(df)
    
    for index, row in df.iterrows():
        url = row.get(url_col)
        progress_msg = f"[{index + 1}/{total_rows}] Checking Link: {url}"
        print(progress_msg)
        if progress_callback:
            progress_callback(progress_msg, is_detail=False)
        
        status = check_url_status(url)
        statuses.append(status)
        
        detail_msg = f"-> Status: {status}"
        print(detail_msg)
        if progress_callback:
            progress_callback(detail_msg, is_detail=True)
        
    df["Status"] = statuses
    df.to_excel(output_file, index=False)
    
    final_msg = f"Link verification completed! Saved to: {output_file}"
    print(final_msg)
    if progress_callback:
        progress_callback(final_msg, is_detail=False)
    
    return output_file

if __name__ == "__main__":
    input_f = sys.argv[1] if len(sys.argv) > 1 else "Ai_checked.xlsx"
    output_f = sys.argv[2] if len(sys.argv) > 2 else "final_output.xlsx"
    run_link_checker(input_file=input_f, output_file=output_f)