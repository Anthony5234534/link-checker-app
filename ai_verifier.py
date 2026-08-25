import os
import json
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
API_KEY = os.getenv("LLM_API_KEY") 
BASE_URL = os.getenv("LLM_BASE_URL", None)
MODEL_NAME = os.getenv("LLM_MODEL", "gpt-4o-mini")

def call_ai_verifier(context, content, custom_prompt):
    if not API_KEY:
        raise ValueError("API Key not found. Please set LLM_API_KEY in your .env file.")

    final_prompt = custom_prompt.replace("{context}", context).replace("{content}", content)

    if LLM_PROVIDER == "claude":
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("Please install anthropic SDK: pip install anthropic")

        client = Anthropic(api_key=API_KEY)
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": final_prompt}]
        )
        res_text = response.content[0].text
        
    else:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Please install openai SDK: pip install openai")

        client_kwargs = {"api_key": API_KEY}
        if BASE_URL:
            client_kwargs["base_url"] = BASE_URL

        client = OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": final_prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        res_text = response.choices[0].message.content

    if "```json" in res_text:
        res_text = res_text.split("```json")[1].split("```")[0].strip()
    elif "```" in res_text:
        res_text = res_text.split("```")[1].strip()

    try:
        return json.loads(res_text)
    except json.JSONDecodeError:
        return {"Result": "error", "Reason": f"Failed to parse AI output: {res_text}"}




def run_ai_verification(input_file="merged_data.xlsx", output_file="Ai_checked.xlsx", prompt=None, additional_info=None, progress_callback=None):
    
    print(f"--- Starting AI Verification ---") 

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_excel(input_file)

    if prompt is None:
        prompt = """
        You are a professional marketing content auditor. Your task is to verify if the "Web Content" (e.g., a social media post, news article, or web page) correctly serves as the supporting evidence for the "Preceding Context" (an excerpt from a business/marketing report).
        
        [Preceding Context]:
        {context}
        
        [Web Content]:
        {content}
        
        [Additional Instructions / Supplementary Info]:
        {additional_info}
        
        ### Evaluation Rules (Strictly Follow):
        1. Nature of Evidence (Crucial): The Web Content is real-world evidence (e.g., a social media post, news article). It will naturally NOT contain internal business metrics, KPIs, or analytical conclusions (e.g., PR value, engagement rates, rankings, MoM growth) mentioned in the Preceding Context. Do NOT mark as "mismatch" just because these business numbers are missing.
        2. Criteria for "match": 
           - They share the same core entities, events, campaigns, themes, or key figures (KOLs/celebrities).
           - Having a clear correlation or hitting the main keywords/hashtags is sufficient for a "match".
           - Strictly follow any specific guidelines, abbreviations, or context provided in the [Additional Instructions / Supplementary Info] section.
        3. Criteria for "mismatch": 
           - The topics are completely unrelated or misaligned (e.g., Context talks about an Art Exhibition, but Web Content is about a Basketball event).
           - The Web Content is clearly an error page, login wall, or expired link (e.g., "Link expired", "Page not found", "页面不见了").

        ### Output Format:
        You MUST return the output STRICTLY in valid JSON format with exactly two keys: "Result" and "Reason".
        - "Result": Must be exactly "match" or "mismatch".
        - "Reason": Must be written in Traditional Chinese (繁體中文). Explain the specific correlation (why they match) or the exact conflict/error (why they mismatch) based on the rules above. Keep it concise and logical.
        """

    info_text = additional_info if additional_info else "None provided."
    prompt = prompt.replace("{additional_info}", info_text)

    results = []
    reasons = []
    total_rows = len(df)

    for index, row in df.iterrows():
        link_url = row.get("Link_URL", f"Row {index+1}")
        context = str(row.get("Preceding_Context", "")).strip()
        content = str(row.get("Content", "")).strip()
        status = str(row.get("Status", "expired")).strip().lower()

        progress_msg = f"[{index + 1}/{total_rows}] Checking Link: {link_url}"
        print(progress_msg)
        if progress_callback:
            progress_callback(progress_msg, is_detail=False)

        if status != "work" or pd.isna(row.get("Content")) or content == "" or content.lower() == "nan":
            res = "no content"
            if status == "expired":
                reas = "連結已失效或遭到平台防護攔截，無法取得網頁內容進行比對。"
            elif status == "error":
                reas = "爬蟲執行過程中發生錯誤，無法取得網頁內容。"
            else:
                reas = "找不到網頁內容，無法進行語意比對。"
                
            results.append(res)
            reasons.append(reas)
            
            detail_msg = f"-> Result: {res}\n-> Reason: {reas}"
            print(detail_msg)
            if progress_callback:
                progress_callback(detail_msg, is_detail=True)
            continue

        try:
            # call_ai_verifier 預期內部會把 {context} 和 {content} 填入
            ai_output = call_ai_verifier(context, content, prompt) 
            res = ai_output.get("Result", "error")
            reas = ai_output.get("Reason", "No reason provided by AI.")
            results.append(res)
            reasons.append(reas)
            
            detail_msg = f"-> Result: {res}\n-> Reason: {reas}"
            print(detail_msg)
            if progress_callback:
                progress_callback(detail_msg, is_detail=True)

        except Exception as e:
            err_msg = f"AI API call failed: {str(e)}"
            results.append("error")
            reasons.append(err_msg)
            
            detail_msg = f"-> Result: error\n-> Reason: {err_msg}"
            print(detail_msg)
            if progress_callback:
                progress_callback(detail_msg, is_detail=True)

    df["Result"] = results
    df["Reason"] = reasons

    df.to_excel(output_file, index=False)
    final_msg = f"AI Verification completed! Saved to: {output_file}"
    print(final_msg)
    if progress_callback:
        progress_callback(final_msg, is_detail=False)
    
    return output_file

