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
if 'step2_output' not in st.session_state:
    st.session_state['step2_output'] = None

# UI Progress Callback helper for real-time logs
def ui_progress_callback(status_placeholder, log_list):
    def callback(message, is_detail=False):
        if not is_detail:
            status_placeholder.markdown(f"**⏳ Status:** `{message}`")
        log_list.append(message)
        display_log = "\n".join(log_list[-20:])
        st.session_state['log_placeholder'].code(display_log, language="text")
    return callback

# ==========================================
# Sidebar Navigation (2 Streamlined Steps)
# ==========================================
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to step:", [
    "1. Extract PPT Links", 
    "2. Scrape & AI Semantic Check"
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
            with st.spinner("Extracting links from presentation..."):
                try:
                    df_extracted = parse_ppt_to_excel(uploaded_ppt)
                    output_filename = f"{sid}_step1_extracted_links.xlsx"
                    df_extracted.to_excel(output_filename, index=False)
                    
                    st.session_state['step1_output'] = output_filename
                    st.success(f"Extraction successful! Found {len(df_extracted)} links.")
                    
                    st.dataframe(df_extracted.head(10))
                    
                    with open(output_filename, "rb") as file:
                        st.download_button(
                            label="Download Extracted Excel",
                            data=file,
                            file_name="extracted_links.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                except Exception as e:
                    st.error(f"An error occurred during extraction: {e}")

# ==========================================
# STEP 2: Scrape Content & AI Semantic Check
# ==========================================
elif page == "2. Scrape & AI Semantic Check":
    st.header("Step 2: Scrape Web Content & Run AI Semantic Check")
    st.write("Perform web content extraction via Apify scraper followed by AI semantic verification in one seamless workflow.")
    
    # Input File Selection
    st.subheader("1. Data Input Source")
    use_default_ppt = st.checkbox("Use output from Step 1 as input file", value=(st.session_state['step1_output'] is not None))
    
    if use_default_ppt and st.session_state['step1_output'] is not None:
        input_file_path = st.session_state['step1_output']
        st.info("Using extracted links data from Step 1.")
    else:
        uploaded_custom_excel = st.file_uploader("Or Upload Custom Excel File (Must contain 'Link_URL')", type=["xlsx"])
        if uploaded_custom_excel:
            input_file_path = f"{sid}_temp_custom_input.xlsx"
            with open(input_file_path, "wb") as f:
                f.write(uploaded_custom_excel.getbuffer())
        else:
            input_file_path = None

    # Prompt Configuration
    st.subheader("2. AI Prompt Configuration")
    st.warning("Note: Your custom prompt MUST contain exactly `{context}` and `{content}` placeholder tags.")
    
    default_prompt = """You are a professional content auditor. Compare the "Preceding Context" with the "Web Content" below.

[Preceding Context]:
{context}

[Web Content]:
{content}

Determine if they match semantically. 
You MUST return the output STRICTLY in JSON format with exactly two keys: "Result" and "Reason".

Rules for JSON keys:
- "Result": Must be exactly "match" or "mismatch".
- "Reason": Must be written in Traditional Chinese (繁體中文). It MUST explain why they match or mismatch (why match / why mismatch)."""

    custom_prompt = st.text_area("Edit AI Prompt:", value=default_prompt, height=250)

    # Execution Button
    st.subheader("3. Run Pipeline")
    if st.button("Start Scraper & AI Verification"):
        if not input_file_path:
            st.error("Please provide a valid input Excel file (either from Step 1 or uploaded manually).")
        elif "{context}" not in custom_prompt or "{content}" not in custom_prompt:
            st.error("Your prompt must contain both '{context}' and '{content}' tags.")
        else:
            st.markdown("### 🔄 Execution Live Logs")
            status_placeholder = st.empty()
            st.session_state['log_placeholder'] = st.empty()
            log_list = []
            callback = ui_progress_callback(status_placeholder, log_list)
            
            try:
                # Stage A: Run Apify Scraper
                callback("Initializing Apify Scraper workflow...", is_detail=False)
                df_input = pd.read_excel(input_file_path)
                
                # Execute scraper
                df_scraped = run_apify_scraper(df_input)
                scraped_temp_path = f"{sid}_temp_scraped.xlsx"
                df_scraped.to_excel(scraped_temp_path, index=False)
                
                callback("Apify Scraper finished successfully! Starting AI semantic verification...", is_detail=False)
                
                # Stage B: Run AI Verifier
                final_output_path = f"{sid}_step2_final_checked.xlsx"
                run_ai_verification(
                    input_file=scraped_temp_path,
                    output_file=final_output_path,
                    prompt=custom_prompt,
                    progress_callback=callback
                )
                
                st.session_state['step2_output'] = final_output_path
                status_placeholder.success("✅ Scrape and AI Verification completed successfully!")
                
                # Display Results Preview
                st.markdown("### 📊 Final Results Preview")
                df_result = pd.read_excel(final_output_path)
                
                # Show columns if available
                display_cols = [c for c in ["Link_URL", "Platform", "Status", "Result", "Reason"] if c in df_result.columns]
                st.dataframe(df_result[display_cols].head(15))
                
                # Download Button
                with open(final_output_path, "rb") as file:
                    st.download_button(
                        label="Download Complete Checked Excel Report",
                        data=file,
                        file_name="final_checked_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
            except Exception as e:
                status_placeholder.error(f"Pipeline execution failed: {e}")