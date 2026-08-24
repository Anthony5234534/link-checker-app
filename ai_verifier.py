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


def run_ai_verification(input_file="merged_data.xlsx", output_file="Ai_checked.xlsx", prompt=None, progress_callback=None):
    """
    讀取合併後的資料：
    - 若 Status 不是 'work' (即 expired/error/invalid)，直接判定 Result 為 'no content'。
    - 若 Status 是 'work'，才呼叫 AI 比對 Preceding_Context 與 Content，輸出 match 或 mismatch。
    """
    print(f"--- Starting AI Verification using [{LLM_PROVIDER.upper()}] Model: {MODEL_NAME} ---")

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_excel(input_file)

    if prompt is None:
        prompt = """
        You are a professional content auditor. Compare the "Preceding Context" with the "Web Content" below.
        
        [Preceding Context]:
        {context}
        
        [Web Content]:
        {content}
        
        Determine if they match semantically. 
        You MUST return the output STRICTLY in JSON format with exactly two keys: "Result" and "Reason".
        
        Rules for JSON keys:
        - "Result": Must be exactly "match" or "mismatch".
        - "Reason": Must be written in Traditional Chinese (繁體中文). It MUST explain why they match or mismatch (why match / why mismatch).
        """

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

        # 💡 核心邏輯修改：如果爬蟲狀態不是 'work' (例如 expired, error 等)，直接給 no content
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

        # 💡 只有在 status == "work" 且有內容時，才呼叫 AI 判斷 match 或 mismatch
        try:
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

if __name__ == "__main__":
    run_ai_verification()