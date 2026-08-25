import os
import uuid
import streamlit as st
import pandas as pd

# Import your core modules
from ppt_extractor import parse_ppt_to_excel
from apify_scraper import run_apify_scraper
from ai_verifier import run_ai_verification

st.set_page_config(page_title="Link Checking & AI Verification Automation", layout="wide")

# ==========================================
# Session State Initialization & Security ID
# ==========================================
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = str(uuid.uuid4())[:8]
sid = st.session_state['session_id']

if 'step1_output' not in st.session_state:
    st.session_state['step1_output'] = None
if 'step2_config' not in st.session_state:
    st.session_state['step2_config'] = {}
if 'step3_output' not in st.session_state:
    st.session_state['step3_output'] = None
if 'step4_output' not in st.session_state:
    st.session_state['step4_output'] = None

# UI Progress Callback helper for real-time logs
def ui_progress_callback(status_placeholder, log_list):
    def callback(message, is_detail=False):
        if not is_detail:
            status_placeholder.markdown(f"**⏳ Status:** `{message}`")
        log_list.append(message)
        display_log = "\n".join(log_list[-20:])
        if 'log_placeholder' in st.session_state:
            st.session_state['log_placeholder'].code(display_log, language="text")
    return callback

# ==========================================
# Sidebar Navigation (4 Streamlined Steps)
# ==========================================
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to step:", [
    "1. Extract PPT Links", 
    "2. API & Model Configuration",
    "3. Scrape Web Content",
    "4. AI Semantic Check"
])

# ==========================================
# STEP 1: Extract Links from PPT
# ==========================================
if page == "1. Extract PPT Links":  
    st.header("Step 1: Extract Links from PPT")
    st.write("Upload a PowerPoint presentation (.pptx) to extract all internal hyperlinks and their preceding text context.")
    
    uploaded_ppt = st.file_uploader("Upload PPT File", type=["pptx"])
    
    if uploaded_ppt is not None:
        if st.button("Extract Links"):
            status_placeholder = st.empty()
            status_placeholder.markdown("**⏳ Status:** `Extracting links from presentation...`")
            
            try:
                df_extracted = parse_ppt_to_excel(uploaded_ppt)
                
                if df_extracted is None or df_extracted.empty:
                    status_placeholder.warning("⚠️ Warning: No hyperlinks were found in this PowerPoint presentation.")
                else:
                    output_filename = f"{sid}_step1_extracted_links.xlsx"
                    df_extracted.to_excel(output_filename, index=False)
                    
                    st.session_state['step1_output'] = output_filename
                    status_placeholder.success(f"✅ Extraction successful! Found {len(df_extracted)} links.")
                    
                    st.markdown("### 📊 Extracted Links Preview")
                    st.dataframe(df_extracted.head(10))
                    
                    with open(output_filename, "rb") as file:
                        st.download_button(
                            label="📥 Download Extracted Excel",
                            data=file,
                            file_name="extracted_links.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            except Exception as e:
                status_placeholder.error(f"❌ An error occurred during extraction: {e}")

# ==========================================
# STEP 2: API & Model Configuration
# ==========================================
elif page == "2. API & Model Configuration":
    st.header("Step 2: API & Model Configuration")
    st.write("Configure your Apify API Token and choose your preferred AI LLM provider, API Key, and model parameters.")
    
    st.subheader("1. Apify API Token")
    saved_apify_token = st.session_state['step2_config'].get("APIFY_API_TOKEN", "")
    
    apify_token_input = st.text_input(
        "APIFY_API_TOKEN", 
        type="password", 
        value=saved_apify_token,
        placeholder="Enter your Apify API token here..."
    )
    
    st.subheader("2. AI LLM Provider & Credentials")
    
    provider_options = ["DeepSeek", "Anthropic (Claude)", "Gemini (Google)"]
    selected_provider_ui = st.selectbox("Select AI Provider", provider_options)
    
    if selected_provider_ui == "DeepSeek":
        llm_provider = "openai"
        default_model = "deepseek-chat"
        default_base_url = "https://api.deepseek.com"
    elif selected_provider_ui == "Anthropic (Claude)":
        llm_provider = "claude"
        default_model = "claude-3-5-sonnet-20241022"
        default_base_url = ""
    elif selected_provider_ui == "Gemini (Google)":
        llm_provider = "openai"
        default_model = "gemini-1.5-pro"
        default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

    saved_api_key = st.session_state['step2_config'].get("LLM_API_KEY", "")
    
    api_key_input = st.text_input(
        f"API Key for {selected_provider_ui}", 
        type="password",
        value=saved_api_key,
        placeholder="Enter your API key here..."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        model_name_input = st.text_input("Model Name", value=default_model)
    with col2:
        base_url_input = st.text_input("Base URL (Optional)", value=default_base_url, placeholder="e.g., https://api.deepseek.com")
        
    if st.button("Save Configuration"):
        if not apify_token_input:
            st.error("APIFY_API_TOKEN is required.")
        elif not api_key_input:
            st.error(f"API Key for {selected_provider_ui} is required.")
        else:
            st.session_state['step2_config'] = {
                "APIFY_API_TOKEN": apify_token_input,
                "LLM_PROVIDER": llm_provider,
                "LLM_API_KEY": api_key_input,
                "LLM_BASE_URL": base_url_input if base_url_input else None,
                "LLM_MODEL": model_name_input
            }
            st.success("✅ Configuration saved successfully! You can now proceed to Step 3.")

    if st.session_state['step2_config']:
        st.info("Current configuration is saved and ready for the pipeline.")

# ==========================================
# STEP 3: Scrape Web Content (Apify Only)
# ==========================================
elif page == "3. Scrape Web Content":
    st.header("Step 3: Scrape Web Content")
    st.write("Perform web content extraction via Apify scraper. This step generates a checkpoint file containing all crawled text.")
    
    if not st.session_state['step2_config']:
        st.warning("⚠️ Please complete Step 2 (API & Model Configuration) first before running the pipeline.")
    
    st.subheader("1. Data Input Source")
    use_default_ppt = st.checkbox("Use output from Step 1 as input file", value=(st.session_state['step1_output'] is not None))
    
    if use_default_ppt and st.session_state['step1_output'] is not None:
        input_file_path = st.session_state['step1_output']
        st.info("Using extracted links data from Step 1.")
    else:
        uploaded_custom_excel = st.file_uploader("Or Upload Custom Excel File (Must contain 'Link_URL')", type=["xlsx"], key="upload_step3")
        if uploaded_custom_excel:
            input_file_path = f"{sid}_temp_custom_input_step3.xlsx"
            with open(input_file_path, "wb") as f:
                f.write(uploaded_custom_excel.getbuffer())
        else:
            input_file_path = None

    st.subheader("2. Run Apify Scraper")
    
    if st.session_state.get('step3_output') and os.path.exists(st.session_state['step3_output']):
        st.success("✅ Previous scraping task completed! You can download the checkpoint file below and proceed to Step 4.")
        try:
            df_result_preview = pd.read_excel(st.session_state['step3_output'])
            st.dataframe(df_result_preview.head(10))
        except Exception:
            pass
        with open(st.session_state['step3_output'], "rb") as file:
            st.download_button(
                label="📥 Download Scraped Checkpoint Excel",
                data=file,
                file_name="scraped_checkpoint.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        st.markdown("---") 

    if st.button("Start Web Scraper"):
        if not st.session_state['step2_config']:
            st.error("Please configure your API keys in Step 2 first.")
        elif not input_file_path:
            st.error("Please provide a valid input Excel file.")
        else:
            config = st.session_state['step2_config']
            os.environ["APIFY_API_TOKEN"] = config["APIFY_API_TOKEN"]

            st.markdown("### 🔄 Execution Live Logs")
            status_placeholder = st.empty()
            st.session_state['log_placeholder'] = st.empty()
            
            results_container = st.container()
            log_list = []
            
            def step3_callback(message, is_detail=False):
                if not is_detail:
                    status_placeholder.markdown(f"**⏳ Status:** `{message}`")
                else:
                    log_list.append(message)
                    with results_container:
                        st.markdown(message)
                    display_log = "\n".join(log_list[-20:])
                    st.session_state['log_placeholder'].code(display_log, language="text")

            try:
                status_placeholder.markdown("**⏳ Status:** `Initializing Apify Scraper workflow...`")
                df_input = pd.read_excel(input_file_path)
                
                df_scraped = run_apify_scraper(df_input, progress_callback=step3_callback)
                scraped_output_path = f"{sid}_step3_scraped.xlsx"
                df_scraped.to_excel(scraped_output_path, index=False)
                
                st.session_state['step3_output'] = scraped_output_path
                status_placeholder.success("✅ Scraper finished! Loading download button...")
                st.rerun() 
                    
            except Exception as e:
                status_placeholder.error(f"Scraper execution failed: {e}")

# ==========================================
# STEP 4: AI Semantic Check
# ==========================================
elif page == "4. AI Semantic Check":
    st.header("Step 4: AI Semantic Check")
    st.write("Run AI semantic verification on the scraped data using your configured LLM credentials.")
    
    if not st.session_state['step2_config']:
        st.warning("⚠️ Please complete Step 2 (API & Model Configuration) first before running the pipeline.")
    
    st.subheader("1. Data Input Source (Checkpoint File)")
    use_default_scraped = st.checkbox("Use scraped checkpoint output from Step 3", value=(st.session_state['step3_output'] is not None))
    
    if use_default_scraped and st.session_state['step3_output'] is not None:
        input_file_path = st.session_state['step3_output']
        st.info("Using scraped checkpoint data from Step 3.")
    else:
        uploaded_custom_excel = st.file_uploader("Or Upload Scraped Excel File (Must contain 'Content' & 'Status' columns)", type=["xlsx"], key="upload_step4")
        if uploaded_custom_excel:
            input_file_path = f"{sid}_temp_custom_input_step4.xlsx"
            with open(input_file_path, "wb") as f:
                f.write(uploaded_custom_excel.getbuffer())
        else:
            input_file_path = None

    st.subheader("2. AI Prompt Configuration")
    st.warning("Note: Your custom prompt MUST contain exactly `{context}` and `{content}` placeholder tags.")
    
    default_prompt = """You are a professional marketing content auditor. Your task is to verify if the "Web Content" (e.g., a social media post, news article, or web page) correctly serves as the supporting evidence for the "Preceding Context" (an excerpt from a business/marketing report).
        
[Preceding Context]:
{context}

[Web Content]:
{content}

### Evaluation Rules (Strictly Follow):
1. Nature of Evidence (Crucial): The Web Content is real-world evidence (e.g., a social media post, news article). It will naturally NOT contain internal business metrics, KPIs, or analytical conclusions (e.g., PR value, engagement rates, rankings, MoM growth) mentioned in the Preceding Context. Do NOT mark as "mismatch" just because these business numbers are missing.
2. Criteria for "match": 
   - They share the same core entities, events, campaigns, themes, or key figures (KOLs/celebrities).
   - Having a clear correlation or hitting the main keywords/hashtags is sufficient for a "match".
3. Criteria for "mismatch": 
   - The topics are completely unrelated or misaligned (e.g., Context talks about an Art Exhibition, but Web Content is about a Basketball event).
   - The Web Content is clearly an error page, login wall, or expired link (e.g., "Link expired", "Page not found", "页面不见了").

### Output Format:
You MUST return the output STRICTLY in valid JSON format with exactly two keys: "Result" and "Reason".
- "Result": Must be exactly "match" or "mismatch".
- "Reason": Must be written in Traditional Chinese (繁體中文). Explain the specific correlation (why they match) or the exact conflict/error (why they mismatch) based on the rules above. Keep it concise and logical."""

    custom_prompt = st.text_area("Edit AI Prompt:", value=default_prompt, height=320)

    st.subheader("3. Run AI Verification")
    
    if st.session_state.get('step4_output') and os.path.exists(st.session_state['step4_output']):
        st.success("✅ AI Verification completed! You can directly download the final report.")
        try:
            df_result_preview = pd.read_excel(st.session_state['step4_output'])
            st.dataframe(df_result_preview.head(10))
        except Exception:
            pass
        with open(st.session_state['step4_output'], "rb") as file:
            st.download_button(
                label="📥 Download Final Checked Excel Report",
                data=file,
                file_name="final_checked_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        st.markdown("---") 

    if st.button("Start AI Verification"):
        if not st.session_state['step2_config']:
            st.error("Please configure your API keys and models in Step 2 first.")
        elif not input_file_path:
            st.error("Please provide a valid input Excel file.")
        elif "{context}" not in custom_prompt or "{content}" not in custom_prompt:
            st.error("Your prompt must contain both '{context}' and '{content}' tags.")
        else:
            config = st.session_state['step2_config']
            os.environ["LLM_PROVIDER"] = config["LLM_PROVIDER"]
            os.environ["LLM_API_KEY"] = config["LLM_API_KEY"]
            if config["LLM_BASE_URL"]:
                os.environ["LLM_BASE_URL"] = config["LLM_BASE_URL"]
            else:
                os.environ.pop("LLM_BASE_URL", None)
            os.environ["LLM_MODEL"] = config["LLM_MODEL"]

            st.markdown("### 🔄 Execution Live Logs & Real-time Results")
            status_placeholder = st.empty()
            st.session_state['log_placeholder'] = st.empty()
            
            results_container = st.container()
            log_list = []
            
            def step4_callback(message, is_detail=False):
                if not is_detail:
                    status_placeholder.markdown(f"**⏳ Status:** `{message}`")
                else:
                    log_list.append(message)
                    with results_container:
                        st.markdown(message)
                    display_log = "\n".join(log_list[-20:])
                    st.session_state['log_placeholder'].code(display_log, language="text")

            try:
                status_placeholder.markdown("**⏳ Status:** `Starting AI semantic verification...`")
                
                final_output_path = f"{sid}_step4_final_checked.xlsx"
                run_ai_verification(
                    input_file=input_file_path,
                    output_file=final_output_path,
                    prompt=custom_prompt,
                    provider=config["LLM_PROVIDER"],
                    api_key=config["LLM_API_KEY"],
                    base_url=config["LLM_BASE_URL"],
                    model_name=config["LLM_MODEL"],
                    progress_callback=step4_callback
                )
                
                st.session_state['step4_output'] = final_output_path
                status_placeholder.success("✅ AI process finished! Loading download button...")
                st.rerun() 
                    
            except Exception as e:
                status_placeholder.error(f"AI Verification failed: {e}")