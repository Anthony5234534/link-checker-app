import pandas as pd
from pptx import Presentation
from urllib.parse import urlparse
from pptx.enum.shapes import MSO_SHAPE_TYPE

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
    """
    Parses a PPT file (either a file path string or a file-like object from Streamlit), 
    extracts links with preceding text context, performs forward filling, 
    and returns a pandas DataFrame.
    """
    # Presentation() accepts both file paths and file-like objects (BytesIO)
    prs = Presentation(ppt_source)
    data = []

    # Iterate through slides
    for slide_index, slide in enumerate(prs.slides):
        slide_num = slide_index + 1
        slide_title = "No Title"
        if slide.shapes.title:
            slide_title = slide.shapes.title.text.strip().replace('\n', ' ')

        # Iterate through shapes in slide
        for shape in iter_shapes(slide.shapes): 
            if not shape.has_text_frame:
                continue

            for paragraph in shape.text_frame.paragraphs:
                runs_info = []
                for run in paragraph.runs:
                    runs_info.append({
                        'text': run.text,
                        'url': run.hyperlink.address if run.hyperlink else None
                    })

                current_preceding = ""
                link_group_context = ""

                for r in runs_info:
                    if r['url']:
                        link_url = r['url']
                        platform = extract_platform(link_url)

                        if current_preceding.strip():
                            cleaned_text = current_preceding.replace('[', '').replace(']', '')
                            link_group_context = cleaned_text.strip().replace('\n', ' ')
                            current_preceding = "" 

                        data.append({
                            'Slide number': slide_num,
                            'Slide_Title': slide_title,
                            'Link_URL': link_url,
                            'Platform': platform,
                            'Preceding_Context': link_group_context
                        })
                    else:
                        current_preceding += r['text']

    df = pd.DataFrame(data)

    # Forward fill context within each slide
    if not df.empty:
        df['Preceding_Context'] = df['Preceding_Context'].replace('', pd.NA)
        df['Preceding_Context'] = df.groupby('Slide number')['Preceding_Context'].ffill()
        df['Preceding_Context'] = df['Preceding_Context'].fillna('')

    print(f"Extraction successful! Total links found: {len(df)}.")
    return df