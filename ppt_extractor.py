import pandas as pd
from pptx import Presentation
from urllib.parse import urlparse
from ppt_parser import iter_ppt_links

# Input: url, Output: platform
def extract_platform(url):
    try:
        if not url.startswith('http'):
            url = 'https://' + url.replace('https//', 'https://')

        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        # Categorization logic
        if 'instagram.com' in domain:
            return 'Instagram'
        elif 'facebook.com' in domain or 'fb.com' in domain:
            return 'Facebook'
        elif 'threads.net' in domain or 'threads.com' in domain:
            return 'Threads'
        elif 'xiaohongshu.com' in domain or 'xhslink.com' in domain:
            return 'Xiaohongshu'
        elif 'douyin.com' in domain:
            return 'Douyin'
        elif 'weibo.com' in domain or 'weibo.cn' in domain:
            return 'Weibo'
        elif 'mp.weixin.qq.com' in domain:
            return 'WeChat Official Account'
        elif 'youtube.com' in domain or 'youtu.be' in domain:
            return 'YouTube'
        else:
            return 'Website'

    except Exception:
        return 'Unknown'

# The main function 
# Input the ppt, Output a dataFrame with Slide number, Slide_Title, Link_URL, Platform, Preceding_Context
def parse_ppt_to_excel(ppt_source):
    prs = Presentation(ppt_source)
    data = []

    for item in iter_ppt_links(prs):
        if item['url'] == "MISSING_URL_MANUAL_REQUIRED":
            platform = "Unknown (Missing Link)"
        else:
            platform = extract_platform(item['url']) 

        data.append({
            'Slide number': item['slide_num'],
            'Slide_Title': item['slide_title'],
            'Link_URL': item['url'],
            'Platform': platform,
            'Preceding_Context': item['preceding_context']
        })

    df = pd.DataFrame(data)

    if not df.empty:
        df['Preceding_Context'] = df['Preceding_Context'].replace(r'^\s*$', pd.NA, regex=True)
        df['Preceding_Context'] = df.groupby('Slide number')['Preceding_Context'].ffill()
        df['Preceding_Context'] = df['Preceding_Context'].fillna('')

    print(f"Extraction successful! Total links found: {len(df)}.")
    return df