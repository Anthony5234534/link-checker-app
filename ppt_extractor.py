import pandas as pd
from pptx import Presentation
from urllib.parse import urlparse
from pptx.enum.shapes import MSO_SHAPE_TYPE
import re

def extract_platform(url):
    """
    Categorize the URL based on domain:
    - Social Media/Content Platforms: Instagram, Facebook, Threads, XHS, etc.
    - Others: News, forums, and general websites are categorized as 'Website'.
    """
    try:
        # Fix missing colon formats (e.g., https//...)
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

def iter_shapes(shapes):
    """Recursively yield all shapes, including those nested inside groups."""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(shape.shapes)
        else:
            yield shape


def parse_ppt_to_excel(ppt_source):
    prs = Presentation(ppt_source)
    data = []

    for slide_index, slide in enumerate(prs.slides):
        slide_num = slide_index + 1
        slide_title = "No Title"
        if slide.shapes.title and slide.shapes.title.text:
            slide_title = slide.shapes.title.text.strip().replace('\n', ' ')

        for shape in iter_shapes(slide.shapes): 
            if not shape.has_text_frame:
                continue

            for paragraph in shape.text_frame.paragraphs:
                current_preceding = "" 
                
                for run in paragraph.runs:
                    text_content = run.text
                    link_url = run.hyperlink.address if run.hyperlink else None
                    
                    if link_url:
                        # 處理累積文字中遺漏網址的 [link]
                        matches = list(re.finditer(r'\[\s*link\s*\]', current_preceding, flags=re.IGNORECASE))
                        last_end = 0
                        
                        for match in matches:
                            context = current_preceding[last_end:match.start()]
                            # 暴力清除所有 [ 與 ]，確保乾淨
                            cleaned_context = re.sub(r'[\[\]]', '', context).strip().replace('\n', ' ')
                            
                            data.append({
                                'Slide number': slide_num,
                                'Slide_Title': slide_title,
                                'Link_URL': "MISSING_URL_MANUAL_REQUIRED",
                                'Platform': "Unknown (Missing Link)",
                                'Preceding_Context': cleaned_context
                            })
                            last_end = match.end()
                        
                        # 處理當前這個真正的超連結
                        context = current_preceding[last_end:]
                        # 同樣暴力清除所有 [ 與 ]
                        cleaned_context = re.sub(r'[\[\]]', '', context).strip().replace('\n', ' ')
                        platform = extract_platform(link_url)
                        
                        data.append({
                            'Slide number': slide_num,
                            'Slide_Title': slide_title,
                            'Link_URL': link_url,
                            'Platform': platform,
                            'Preceding_Context': cleaned_context
                        })
                        
                        current_preceding = ""
                        
                    else:
                        current_preceding += text_content
                
                # 處理段落結尾可能殘留的 [link]
                matches = list(re.finditer(r'\[\s*link\s*\]', current_preceding, flags=re.IGNORECASE))
                last_end = 0
                for match in matches:
                    context = current_preceding[last_end:match.start()]
                    cleaned_context = re.sub(r'[\[\]]', '', context).strip().replace('\n', ' ')
                    
                    data.append({
                        'Slide number': slide_num,
                        'Slide_Title': slide_title,
                        'Link_URL': "MISSING_URL_MANUAL_REQUIRED",
                        'Platform': "Unknown (Missing Link)",
                        'Preceding_Context': cleaned_context
                    })
                    last_end = match.end()

    df = pd.DataFrame(data)

    if not df.empty:
        # 強制替換純空白字串為 pd.NA，確保 ffill 能完美覆蓋到所有連續的連結
        df['Preceding_Context'] = df['Preceding_Context'].replace(r'^\s*$', pd.NA, regex=True)
        df['Preceding_Context'] = df.groupby('Slide number')['Preceding_Context'].ffill()
        df['Preceding_Context'] = df['Preceding_Context'].fillna('')

    print(f"Extraction successful! Total links found: {len(df)}.")
    return df