import streamlit as st
import pandas as pd
import os
import uuid  # 產生獨一無二的使用者 ID

from ppt_extractor import parse_ppt_to_excel
from merge_content import merge_link_content
from ai_verifier import run_ai_verification
from link_checker import run_link_checker

st.set_page_config(page_title="Link Checking Automation", layout="wide")

# ==========================================
# 隱私安全升級：為每個連線的使用者產生專屬 Session ID
# ==========================================
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = str(uuid.uuid4())[:8]

sid = st.session_state['session_id']

# 初始化步驟間傳遞的檔案路徑
if 'step1_output' not in st.session_state:
    st.session_state['step1_output'] = None
if 'step2_output' not in st.session_state:
    st.session_state['step2_output'] = None
if 'step3_output' not in st.session_state:
    st.session_state['step3_output'] = None

def ui_progress_callback(status_placeholder, log_list):
    def callback(message, is_detail=False):
        if not is_detail:
            status_placeholder.markdown(f"**⏳ Processing:** `{message}`")
        log_list.append(message)
        display_log = "\n".join(log_list[-15:])
        st.session_state['log_placeholder'].code(display_log, language="text")
    return callback

# ==========================================
# Sidebar 導覽列 (4 個步驟)
# ==========================================
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to step:", [
    "1. Extract PPT Links", 
    "2. Merge Content", 
    "3. AI Semantic Check",
    "4. Final Link Status Check"
])

# ==========================================
# PAGE 1: Extract Links from PPT
# ==========================================
if page == "1. Extract PPT Links":
    st.header("Step 1: Extract Links from PPT")
    st.write("Upload a PowerPoint presentation (.pptx) to extract all links and their preceding context.")
    
    uploaded_ppt = st.file_uploader("Upload PPT File", type=["pptx"])
    
    if uploaded_ppt is not None:
        if st.button("Extract Links"):
            with st.spinner("Extracting links..."):
                try:
                    df_extracted = parse_ppt_to_excel(uploaded_ppt)
                    
                    output_filename = f"{sid}_step1_extracted_links.xlsx"
                    df_extracted.to_excel(output_filename, index=False)
                    st.session_state['step1_output'] = output_filename
                    
                    st.success(f"Extraction successful! Found {len(df_extracted)} links.")
                    st.dataframe(df_extracted.head())
                    
                    with open(output_filename, "rb") as file:
                        st.download_button(
                            label="Download Extracted Excel",
                            data=file,
                            file_name="extracted_links.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                except Exception as e:
                    st.error(f"An error occurred: {e}")

# ==========================================
# PAGE 2: Merge Content
# ==========================================
elif page == "2. Merge Content":
    st.header("Step 2: Merge Target & Source Data")
    st.write("Merge your extracted PPT links (Target) with web scraping content (Source).")
    
    st.subheader("Target File (PPT Data)")
    use_default_ppt = st.checkbox("Use output from Step 1 as Target File", value=(st.session_state['step1_output'] is not None))
    
    if use_default_ppt and st.session_state['step1_output'] is not None:
        target_file_path = st.session_state['step1_output']
        st.info("Using data from Step 1.")
    else:
        target_file_upload = st.file_uploader("Upload Target Excel", type=["xlsx"], key="t_up")
        if target_file_upload:
            target_file_path = f"{sid}_temp_target.xlsx"
            with open(target_file_path, "wb") as f:
                f.write(target_file_upload.getbuffer())
        else:
            target_file_path = None

    st.subheader("Source File (Web Scraping Data)")
    st.markdown("⚠️ **Note:** Your Excel file MUST contain **`URL`** and **`Content`** columns.")
    source_file_upload = st.file_uploader("Upload Source Excel (Supports multi-tab)", type=["xlsx"], key="s_up")
    
    selected_sheet = 0 # 預設讀取第一個 Tab
    
    if source_file_upload is not None:
        source_file_path = f"{sid}_temp_source.xlsx"
        with open(source_file_path, "wb") as f:
            f.write(source_file_upload.getbuffer())
            
        # 💡 聰明功能：動態偵測上傳的 Excel 檔案有哪些 Tab 頁籤！
        try:
            excel_file = pd.ExcelFile(source_file_path)
            sheet_names = excel_file.sheet_names
            
            if len(sheet_names) > 1:
                st.info(f"Detected {len(sheet_names)} tabs in the Excel file.")
                # 讓使用者選擇要讀取哪一個 Tab，或者選擇全部合併
                sheet_options = ["--- Combine All Tabs (合併所有分頁) ---"] + sheet_names
                chosen_option = st.selectbox("Select which tab to read from Source Excel:", sheet_options)
                
                if chosen_option == "--- Combine All Tabs (合併所有分頁) ---":
                    selected_sheet = "ALL_SHEETS"
                else:
                    selected_sheet = chosen_option
            else:
                st.success(f"Excel has 1 tab: '{sheet_names[0]}'")
                selected_sheet = sheet_names[0]
                
        except Exception as e:
            st.warning(f"Could not read sheet names: {e}")
    else:
        source_file_path = None

    if st.button("Run Merge"):
        if not target_file_path or not source_file_upload:
            st.error("Please provide both Target and Source Excel files.")
        else:
            with st.spinner("Merging data..."):
                try:
                    merged_output_path = f"{sid}_step2_merged.xlsx"
                    # 傳入選定的 sheet_name 參數
                    merge_link_content(target_file_path, source_file_path, merged_output_path, sheet_name=selected_sheet)
                    
                    st.session_state['step2_output'] = merged_output_path
                    st.success("✅ Data merged successfully!")
                    
                    df_merged = pd.read_excel(merged_output_path)
                    st.dataframe(df_merged.head())
                    
                    with open(merged_output_path, "rb") as file:
                        st.download_button(
                            "Download Merged Excel", 
                            data=file, 
                            file_name="merged_data.xlsx", 
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                except Exception as e:
                    st.error(f"Merge failed: {e}")
# ==========================================
# PAGE 3: AI Semantic Check
# ==========================================
elif page == "3. AI Semantic Check":
    st.header("Step 3: AI Semantic Verification")
    
    st.subheader("Data Input")
    use_default_merge = st.checkbox("Use merged output from Step 2 as Input File", value=(st.session_state['step2_output'] is not None))
    
    if use_default_merge and st.session_state['step2_output'] is not None:
        input_file_path = st.session_state['step2_output']
        st.info("Using data from Step 2.")
    else:
        input_file_upload = st.file_uploader("Upload Merged Excel File", type=["xlsx"])
        if input_file_upload:
            input_file_path = f"{sid}_temp_ai_input.xlsx"
            with open(input_file_path, "wb") as f:
                f.write(input_file_upload.getbuffer())
        else:
            input_file_path = None

    st.subheader("AI Prompt Configuration")
    st.warning("Note: Your prompt MUST contain exactly `{context}` and `{content}` where the variables should be injected.")
    default_prompt = """You are a professional content auditor. Compare the "Preceding Context" with the "Web Content" below.
        
[Preceding Context]:
{context}

[Web Content]:
{content}

Determine if they match semantically. 
You MUST return the output STRICTLY in JSON format with exactly two keys: "Result" and "Reason".

Rules for JSON keys:
- "Result": Must be exactly "match" or "mismatch".
- "Reason": Must be written in Traditional Chinese (繁體中文). It MUST explain:
    1. What the preceding context is talking about.
    2. What the web content is talking about.
    3. Why they match or mismatch."""
    
    custom_prompt = st.text_area("Edit Prompt:", value=default_prompt, height=300)

    if st.button("Run AI Verification"):
        if not input_file_path:
            st.error("Please provide an input Excel file.")
        elif "{context}" not in custom_prompt or "{content}" not in custom_prompt:
            st.error("Your prompt must contain '{context}' and '{content}' tags.")
        else:
            st.markdown("### Process Log")
            status_placeholder = st.empty()
            st.session_state['log_placeholder'] = st.empty()
            log_list = []
            callback = ui_progress_callback(status_placeholder, log_list)
            
            try:
                final_ai_output_path = f"{sid}_step3_ai_checked.xlsx"
                run_ai_verification(
                    input_file=input_file_path, 
                    output_file=final_ai_output_path, 
                    prompt=custom_prompt,
                    progress_callback=callback
                )
                
                st.session_state['step3_output'] = final_ai_output_path
                status_placeholder.success("✅ AI Verification completed successfully!")
                
                df_result = pd.read_excel(final_ai_output_path)
                st.dataframe(df_result[["Link_URL", "Result", "Reason"]].head())
                
                with open(final_ai_output_path, "rb") as file:
                    st.download_button(
                        "Download AI Checked Excel", 
                        data=file, 
                        file_name="ai_checked_result.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"AI Verification failed: {e}")

# ==========================================
# PAGE 4: Link Status Checker
# ==========================================
elif page == "4. Final Link Status Check":
    st.header("Step 4: Final Link Status Checker")
    st.info("⚠️ **Note:** This feature is currently in the testing stage. Please be aware that the results may not be 100% accurate.")
    st.write("Checks if the URLs are physically reachable, expired, or removed.")
    
    use_default_ai = st.checkbox("Use AI checked output from Step 3 as Input File", value=(st.session_state['step3_output'] is not None))
    
    if use_default_ai and st.session_state['step3_output'] is not None:
        input_file_path = st.session_state['step3_output']
        st.info("Using data from Step 3.")
    else:
        input_file_upload = st.file_uploader("Upload Excel File (Must contain 'Link_URL' or 'URL')", type=["xlsx"])
        if input_file_upload:
            input_file_path = f"{sid}_temp_status_input.xlsx"
            with open(input_file_path, "wb") as f:
                f.write(input_file_upload.getbuffer())
        else:
            input_file_path = None
            
    if st.button("Run Link Checker"):
        if not input_file_path:
            st.error("Please provide an input Excel file.")
        else:
            st.markdown("### Process Log")
            status_placeholder = st.empty()
            st.session_state['log_placeholder'] = st.empty()
            log_list = []
            callback = ui_progress_callback(status_placeholder, log_list)
            
            try:
                final_status_output_path = f"{sid}_step4_final_output.xlsx"
                run_link_checker(
                    input_file=input_file_path, 
                    output_file=final_status_output_path,
                    progress_callback=callback
                )
                
                status_placeholder.success("✅ Link Status Check completed successfully!")
                
                df_result = pd.read_excel(final_status_output_path)
                st.dataframe(df_result[["Link_URL", "Status"]].head(10))
                
                with open(final_status_output_path, "rb") as file:
                    st.download_button(
                        "Download Final Complete Excel", 
                        data=file, 
                        file_name="final_status_checked.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"Link checking failed: {e}")