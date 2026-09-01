import os
import uuid
import streamlit as st
import pandas as pd
import threading
import time


from ppt_extractor import parse_ppt_to_excel
from apify_scraper import run_apify_scraper
from ai_verifier import run_ai_verification, DEFAULT_PROMPT
from highlight_ppt import highlight_presentation
from step4_worker import get_step4_registry, _step4_worker

step4_jobs = get_step4_registry()
st.set_page_config(page_title="Link Checking & AI Verification Automation", layout="wide")


# Session State Initialization & Security ID
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

# Sidebar Navigation (5 Streamlined Steps)

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to step:", [
    "1. Extract PPT Links", 
    "2. API & Model Configuration",
    "3. Scrape Web Content",
    "4. AI Semantic Check", 
    "5. Output Highlighted PPT"
])

# ==========================================
# STEP 1: Extract Links from PPT

if page == "1. Extract PPT Links":  

    st.header("Step 1: Extract Links from PPT  \n[![GitHub Guide](https://img.shields.io/badge/Guide-View_Step_1_Docs-blue?logo=github)](https://github.com/Anthony5234534/link-checker-app/tree/main#step-1-extract-ppt-links)")
    st.info(
        "**📢 Update (Aug 30, 2026): Optimized Extraction & Expanded Platform Support**\n\n"
        "* **PPT Context Extraction Rules:**\n"
        "   * **Text Boxes:** If a text box contains only a single link, the system will now automatically extract all the text within that text box as context.\n"
        "   * **Tables:** If a link is located inside a table cell, the system automatically extracts the text content of the entire row or column containing the link. For detailed implementation logic, please refer to [ppt_parser.py on GitHub](https://github.com/Anthony5234534/link-checker-app/blob/main/ppt_parser.py).\n"
        "* **Instagram Updates:** Now supports scraping both the **author (account name)** and **post date**, allowing users to cross-check if they match the ppt content.\n"
        "* **Facebook Updates:** **Reels and video content** are now supported for scraping (Note: posts/stories are still not supported). Details of platform supported can be found in [GitHub Limitations Guide](https://github.com/Anthony5234534/link-checker-app/tree/main#3-limitations--platform-support)\n"
    )

    st.write("Upload a PowerPoint presentation (.pptx) to extract all internal hyperlinks and their preceding text context.")
    
    uploaded_ppt = st.file_uploader("Upload PPT File", type=["pptx"])
    
    if uploaded_ppt is not None:
        temp_ppt_path = f"{sid}_original_input.pptx"
        with open(temp_ppt_path, "wb") as f:
            f.write(uploaded_ppt.getbuffer())
        st.session_state['step1_ppt_path'] = temp_ppt_path

        if st.button("Extract Links"):
            status_placeholder = st.empty()
            status_placeholder.markdown("**Status:** `Extracting links from presentation...`")
            
            try:
                df_extracted = parse_ppt_to_excel(uploaded_ppt)
                
                if df_extracted is None or df_extracted.empty:
                    status_placeholder.warning("Warning: No hyperlinks were found in this PowerPoint presentation.")
                else:
                    output_filename = f"{sid}_step1_extracted_links.xlsx"
                    df_extracted.to_excel(output_filename, index=False)
                    
                    st.session_state['step1_output'] = output_filename
                    status_placeholder.success(f"Extraction successful! Found {len(df_extracted)} links.")
                    
                    st.markdown("### Extracted Links Preview")
                    st.dataframe(df_extracted.head(10))
                    
                    with open(output_filename, "rb") as file:
                        st.download_button(
                            label="Download Extracted Excel",
                            data=file,
                            file_name="extracted_links.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            except Exception as e:
                status_placeholder.error(f"An error occurred during extraction: {e}")

# ==========================================
# STEP 2: API & Model Configuration

elif page == "2. API & Model Configuration":
    st.header("Step 2: API & Model Configuration \n[![GitHub Guide](https://img.shields.io/badge/Guide-View_Step_2_Docs-blue?logo=github)](https://github.com/Anthony5234534/link-checker-app/tree/main#step-2-api--model-configuration)")
    st.write("Configure your Apify API Token and choose your preferred AI LLM provider, API Key, and model parameters.")

    st.info(
        "**API Key Usage:**\n"
        "* **Apify API Key:** Used to scrape web content from the links extracted in Step 1.\n"
        "* **LLM API Key:** Used to run semantic AI checks to verify if the scraped website content aligns with the PPT context.\n\n"
        "* You can create an account to get a free API key here: [Apify Sign Up](https://apify.com/?fpr=main&gad_source=1&gad_campaignid=23697698574&gbraid=0AAAABARqcXPSEcYu1SHTO9-zJ9F4MKY2_&gclid=Cj0KCQjwhsrUBhDxARIsAN3AQSeBnu-FoNaEqDCzPkFxutuEP-bBcv6V_TYvdzdfy-46GJdLzD5hujwaAoUMEALw_wcB)"
    )
    
    st.subheader("1. Apify API Token")
    saved_apify_token = st.session_state['step2_config'].get("APIFY_API_TOKEN", "")
    
    apify_token_input = st.text_input(
        "APIFY_API_TOKEN", 
        type="password", 
        value=saved_apify_token,
        placeholder="Enter your Apify API token here..."
    )
    
    st.subheader("2. AI LLM Provider & Credentials")

    st.warning(
        "**Note on LLM API Keys:** If you are not using a direct API, you can simply enter dummy or placeholder values (e.g., `XXX`) to pass configuration validation. You can then skip Step 4 entirely and perform your audit using the [Copilot Web Interface](https://copilot.microsoft.com) with a deep-thinking model. (Using the built-in Excel Copilot is **not** recommended)."
    )
    
    provider_options = ["DeepSeek", "Anthropic (Claude)", "Gemini (Google)", "OpenRouter"]
    selected_provider_ui = st.selectbox("Select AI Provider", provider_options)
    
    if selected_provider_ui == "DeepSeek":
        llm_provider = "openai"
    elif selected_provider_ui == "Anthropic (Claude)":
        llm_provider = "claude"
    elif selected_provider_ui == "Gemini (Google)":
        llm_provider = "openai"
    elif selected_provider_ui == "OpenRouter":
        llm_provider = "openai"

    saved_api_key = st.session_state['step2_config'].get("LLM_API_KEY", "")
    
    api_key_input = st.text_input(
        f"API Key for {selected_provider_ui}", 
        type="password",
        value=saved_api_key,
        placeholder="Enter your API key here..."
    )
    
    saved_model_name = st.session_state['step2_config'].get("LLM_MODEL", "")
    saved_base_url = st.session_state['step2_config'].get("LLM_BASE_URL", "")

    col1, col2 = st.columns(2)
    with col1:
        model_name_input = st.text_input("Model Name (Required)", value=saved_model_name, placeholder="e.g., deepseek-chat, google/gemini-2.0-flash-001")
    with col2:
        base_url_input = st.text_input("Base URL (Optional)", value=saved_base_url if saved_base_url else "", placeholder="e.g., https://openrouter.ai/api/v1")
        
    if st.button("Save Configuration"):
        if not apify_token_input:
            st.error("APIFY_API_TOKEN is required.")
        elif not api_key_input:
            st.error(f"API Key for {selected_provider_ui} is required.")
        elif not model_name_input:
            st.error("Model Name is required! Please input the exact model name.")
        else:
            st.session_state['step2_config'] = {
                "APIFY_API_TOKEN": apify_token_input,
                "LLM_PROVIDER": llm_provider,
                "LLM_API_KEY": api_key_input,
                "LLM_BASE_URL": base_url_input if base_url_input.strip() != "" else None,
                "LLM_MODEL": model_name_input
            }
            st.success("Configuration saved successfully! You can now proceed to Step 3.")

    if st.session_state['step2_config']:
        st.info("Current configuration is saved and ready for the pipeline.")

# ==========================================
# STEP 3: Scrape Web Content (Apify Only)



elif page == "3. Scrape Web Content":
    st.header("Step 3: Scrape Web Content  \n[![GitHub Guide](https://img.shields.io/badge/Guide-View_Step_3_Docs-blue?logo=github)](https://github.com/Anthony5234534/link-checker-app/tree/main#step-3-scrape-web-content)")
    st.write("Perform web content extraction via Apify scraper. This step generates a checkpoint file containing all crawled text.")
    
    if not st.session_state['step2_config']:
        st.warning("Please complete Step 2 (API & Model Configuration) first before running the pipeline.")
    
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

    st.warning(
        "**Estimated Time:** The scraping process takes a while \n"
    )
    
    if st.session_state.get('step3_output') and os.path.exists(st.session_state['step3_output']):
        st.success("Previous scraping task completed! You can download the checkpoint file below and proceed to Step 4.")
        try:
            df_result_preview = pd.read_excel(st.session_state['step3_output'])
            st.dataframe(df_result_preview.head(10))
        except Exception:
            pass
        with open(st.session_state['step3_output'], "rb") as file:
            st.download_button(
                label="Download Scraped Checkpoint Excel",
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

            st.markdown("### Execution Live Logs")
            status_placeholder = st.empty()
            st.session_state['log_placeholder'] = st.empty()
            
            results_container = st.container()
            log_list = []
            
            def step3_callback(message, is_detail=False):
                if not is_detail:
                    status_placeholder.markdown(f"**Status:** `{message}`")
                else:
                    log_list.append(message)
                    with results_container:
                        st.markdown(message)
                    display_log = "\n".join(log_list[-20:])
                    st.session_state['log_placeholder'].code(display_log, language="text")

            try:
                status_placeholder.markdown("**Status:** `Initializing Apify Scraper workflow...`")
                df_input = pd.read_excel(input_file_path)
                
                df_scraped = run_apify_scraper(df_input, progress_callback=step3_callback)
                scraped_output_path = f"{sid}_step3_scraped.xlsx"
                df_scraped.to_excel(scraped_output_path, index=False)
                
                st.session_state['step3_output'] = scraped_output_path
                status_placeholder.success("Scraper finished! Loading download button...")
                st.rerun() 
                    
            except Exception as e:
                status_placeholder.error(f"Scraper execution failed: {e}")

# ==========================================
# STEP 4: AI Semantic Check

elif page == "4. AI Semantic Check":
    st.header("Step 4: AI Semantic Check  \n[![GitHub Guide](https://img.shields.io/badge/Guide-View_Step_4_Docs-blue?logo=github)](https://github.com/Anthony5234534/link-checker-app/tree/main#step-4-ai-semantic-check-two-ways)")
    st.write("Run AI semantic verification on the scraped data using your configured LLM credentials.")

    if not st.session_state['step2_config']:
        st.warning("Please complete Step 2 (API & Model Configuration) first before running the pipeline.")

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

    st.info(
        "**Execution Options & Guidelines**\n\n"
        "**Tips for Free Users:**\n"
        "* Using the [Copilot Web Interface](https://copilot.microsoft.com) (selecting a deep thinking model) is recommended or other free AI chat platforms. You can skip Step 4 entirely and run your audit in AI platform.\n"
        "* Excel Copilot Warning:** Using the built-in Excel Copilot is not recommended since it is not designed to handle long-text reading and deep reasoning.\n"
        "* *[View the default chat prompt template here](https://github.com/Anthony5234534/link-checker-app/blob/main/prompt.txt)*\n\n"
        "**Tips for API Users:**\n"
        "* This step now runs in the background. You can safely switch tabs or apps — progress is saved to a checkpoint file every 10 rows, and you can resume from where it stopped.\n"
    )

    st.warning(
        ":red[**Important:** The default prompt is merely a baseline template for convenience and is not guaranteed to be 100% accurate for all scenarios. To achieve high accuracy, examine your scraped data from Step 3 and **custom-design your prompt**.]\n\n"
        "⚠️ **Placeholder Requirement:** Your custom prompt must contain the exact `{context}` and `{content}` placeholder tags. For detailed reasons, please refer to the [GitHub Guide](https://github.com/Anthony5234534/link-checker-app/tree/main#step-4-ai-semantic-check-two-ways)."
    )

    custom_prompt = st.text_area("Edit AI Prompt:", value=DEFAULT_PROMPT, height=320)

    st.subheader("3. Run AI Verification")

    checkpoint_path = f"{sid}_step4_checkpoint.xlsx"
    job = step4_jobs.get(sid)

    # Read from the checkpoint file on disk to get the actual completed row count.
    # This is the single source of truth, regardless of whether the background thread
    # is alive, finished, or unexpectedly died.
    disk_done = 0
    if os.path.exists(checkpoint_path):
        try:
            disk_done = len(pd.read_excel(checkpoint_path))
        except Exception:
            disk_done = 0

    total_rows = None
    if input_file_path and os.path.exists(input_file_path):
        try:
            total_rows = len(pd.read_excel(input_file_path))
        except Exception:
            total_rows = None

    thread_running = (job is not None) and (job.get('thread') is not None) and job['thread'].is_alive()

    # ---- Status display ----
    if thread_running:
        with job['lock']:
            done = job['done']
            total = job['total'] or total_rows or 0
            logs = list(job['logs'])
            err = job['error']

        st.info(f"⏳ AI verification is running in the background... click 'Refresh progress' to see the latest status")
        if total:
            st.progress(min(done / total, 1.0))
        st.code("\n".join(logs[-20:]) if logs else "(No detailed logs yet)", language="text")

        col_a, col_b = st.columns([1, 3])
        with col_a:
            if st.button("🔄 Refresh progress"):
                st.rerun()
        with col_b:
            st.caption("The background thread is still running. You can safely switch tabs or other apps and come back later to click 'Refresh progress' to see the latest status. No need to stay on this page.")

    else:
        if job is not None and job.get('error'):
            st.error(f"⚠️ An error occurred during the previous AI verification: {job['error']}\n\nCurrently completed {disk_done} records. You can click the button below to resume from where it left off.")
        elif os.path.exists(checkpoint_path) and total_rows and 0 < disk_done < total_rows:
            st.warning(
                f"⚠️ Detected incomplete verification progress: **Completed {disk_done} / {total_rows}** records"
                f" (possibly due to connection interruption or the page being closed by the system).\n\n"
                f"Click the button below to automatically resume from row **{disk_done + 1}**. Already completed rows will not be re-run, and no extra API charges will be incurred."
            )

    # If the checkpoint has finished all data, mark it as final output
    if os.path.exists(checkpoint_path) and total_rows and total_rows > 0 and disk_done >= total_rows:
        st.session_state['step4_output'] = checkpoint_path

    if st.session_state.get('step4_output') and os.path.exists(st.session_state['step4_output']):
        st.success("AI Verification completed! You can directly download the final report.")
        try:
            df_result_preview = pd.read_excel(st.session_state['step4_output'])
            st.dataframe(df_result_preview.head(10))
        except Exception:
            pass
        with open(st.session_state['step4_output'], "rb") as file:
            st.download_button(
                label="Download Final Checked Excel Report",
                data=file,
                file_name="final_checked_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_step4_permanent"
            )
        st.markdown("---")

    button_label = "Start AI Verification" if disk_done == 0 else f"▶ Resume AI Verification (from row {disk_done + 1})"

    if st.button(button_label, disabled=thread_running):
        if not st.session_state['step2_config']:
            st.error("Please configure your API keys and models in Step 2 first.")
        elif not input_file_path:
            st.error("Please provide a valid input Excel file.")
        elif "{context}" not in custom_prompt or "{content}" not in custom_prompt:
            st.error("Your prompt must contain both '{context}' and '{content}' tags.")
        else:
            config = st.session_state['step2_config']

            new_job = {
                'thread': None,
                'done': disk_done,
                'total': total_rows or 0,
                'finished': False,
                'error': None,
                'logs': [],
                'last_update': time.time(),
                'lock': threading.Lock(),
            }

            t = threading.Thread(
                target=_step4_worker,
                args=(sid, input_file_path, custom_prompt, config, checkpoint_path, new_job),
                daemon=True
            )
            new_job['thread'] = t
            step4_jobs[sid] = new_job
            t.start()

            st.info("✅ AI verification started in the background. You can now safely switch tabs or applications. Come back later and click 'Refresh progress' to see the results.")
            time.sleep(1)
            st.rerun()

# ==========================================
# STEP 5: Output Highlighted PPT

elif page == "5. Output Highlighted PPT":
    st.header("Step 5: Output Highlighted PPT  \n[![GitHub Guide](https://img.shields.io/badge/Guide-View_Step_5_Docs-blue?logo=github)](https://github.com/Anthony5234534/link-checker-app/tree/main#step-5-output-highlighted-ppt)")
    
    st.write("Generate a final PowerPoint presentation with links highlighted based on their audit status. "
             "(Green = Match, Red = Mismatch, Yellow = Broken/No Content).")

    st.warning(
        "**Important Data Consistency Warning:**\n\n"
        "* The row count, order, and structure of the Excel data from Step 1 **must not** be changed or altered.\n"
        "* The original PPT file must correspond directly to the data processed in the pipeline. Altering the underlying PPT or Excel structure will result in index mismatch errors during highlighting."
    )

    # --- PPT Input Selection ---
    st.subheader("1. Original PPT Input")
    
    has_step1_ppt = st.session_state.get('step1_ppt_path') is not None
    use_default_ppt = st.checkbox("Use PPT uploaded in Step 1", value=has_step1_ppt)
    
    ppt_input_path = None
    if use_default_ppt and has_step1_ppt:
        st.info("Using the presentation originally uploaded in Step 1.")
        ppt_input_path = st.session_state['step1_ppt_path']
    else:
        uploaded_custom_ppt = st.file_uploader("Upload Original PPT File (.pptx)", type=["pptx"], key="upload_ppt_step5")
        if uploaded_custom_ppt:
            ppt_input_path = f"{sid}_temp_input_step5.pptx"
            with open(ppt_input_path, "wb") as f:
                f.write(uploaded_custom_ppt.getbuffer())

    # --- Excel Input Selection ---
    st.subheader("2. Audited Excel Input")
    use_default_excel = st.checkbox("Use automated AI output from Step 4", value=(st.session_state.get('step4_output') is not None))
    
    excel_input_path = None
    if use_default_excel and st.session_state.get('step4_output') is not None:
        st.info("Using AI Verification results from Step 4.")
        excel_input_path = st.session_state['step4_output']
    else:
        st.info("If you skipped Step 4 (e.g., used Copilot manually), upload your completed Excel file here.")
        uploaded_custom_excel = st.file_uploader("Upload Audited Excel (Must contain 'Status' and 'Result')", type=["xlsx"], key="upload_excel_step5")
        if uploaded_custom_excel:
            excel_input_path = f"{sid}_temp_excel_step5.xlsx"
            with open(excel_input_path, "wb") as f:
                f.write(uploaded_custom_excel.getbuffer())
            
            # Validation check for required columns
            try:
                df_check = pd.read_excel(excel_input_path)
                if 'Status' not in df_check.columns or 'Result' not in df_check.columns:
                    st.error("The uploaded Excel file is missing the required 'Status' or 'Result' columns.")
                    excel_input_path = None
            except Exception as e:
                st.error(f"Error reading Excel: {e}")
                excel_input_path = None

    # --- Display Previous Output ---
    if st.session_state.get('step5_output') and os.path.exists(st.session_state['step5_output']):
        st.success("Highlighted PPT generated successfully!")
        with open(st.session_state['step5_output'], "rb") as file:
            st.download_button(
                label="Download Highlighted PPT",
                data=file,
                file_name="highlighted_presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
        st.markdown("---")

    # --- Run Generation ---
    if st.button("Generate Highlighted PPT"):
        if not ppt_input_path:
            st.error("Please provide a valid original PPT file.")
        elif not excel_input_path:
            st.error("Please provide a valid audited Excel file.")
        else:
            status_placeholder = st.empty()
            status_placeholder.markdown("**Status:** `Generating highlighted presentation...`")
            
            try:
                final_ppt_output_path = f"{sid}_step5_highlighted.pptx"
                
                # Execute the highlight function
                highlight_presentation(
                    pptx_path=ppt_input_path,
                    excel_path=excel_input_path,
                    output_path=final_ppt_output_path
                )
                
                st.session_state['step5_output'] = final_ppt_output_path
                status_placeholder.success("Generation finished! Loading download button...")
                st.rerun()
                
            except Exception as e:
                status_placeholder.error(f"Failed to generate presentation: {e}")

st.divider()
st.caption(
    "⚠️ **Disclaimer / 免責聲明：** "
    "Do not rely 100% on AI output. Users must verify critical findings manually before finalizing reports. "
    "The software is provided 'as is', and authors or copyright holders shall not be liable for any claims or damages. "
    "(請勿 100% 盲目信任 AI 輸出結果；使用者應手動覆核關鍵數據。本軟體依「現狀」提供，作者或版權持有人對任何索賠或損害均不承擔責任。)"
)