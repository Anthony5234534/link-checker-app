import os
import pandas as pd

def merge_link_content(target_file, source_file="LinkContent.xlsx", output_file="final_output.xlsx", sheet_name=0):
    """
    Merge the target file with the source file based on the URL.
    Supports selecting a specific sheet_name (can be string name or index, or None for all sheets).
    """
    print(f"Reading target file: {target_file} and source file: {source_file} (Sheet: {sheet_name})...")
    
    if not os.path.exists(target_file):
        raise FileNotFoundError(f"Target file not found: {target_file}")
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Source file not found: {source_file}")
        
    df_target = pd.read_excel(target_file)
    
    # --- 關鍵修改：支援讀取指定的 Sheet，或是把全部 Sheet 合併 ---
    if sheet_name == "ALL_SHEETS":
        # 如果使用者選擇「合併所有 Tab」
        all_sheets_dict = pd.read_excel(source_file, sheet_name=None) # 讀取所有 sheet 變成一個 dict
        df_source = pd.concat(all_sheets_dict.values(), ignore_index=True)
    else:
        # 讀取使用者指定的單一 Sheet
        df_source = pd.read_excel(source_file, sheet_name=sheet_name)
    
    target_link_col = "Link_URL"
    source_link_col = "URL"
    
    if target_link_col not in df_target.columns:
        raise ValueError(f"Error: Cannot find '{target_link_col}' or 'URL' column in target file.")
    if source_link_col not in df_source.columns:
        raise ValueError(f"Error: Column '{source_link_col}' not found in source file. (Please check if your source sheet contains 'URL' column)")

    df_target[target_link_col] = df_target[target_link_col].astype(str).str.strip()
    df_source[source_link_col] = df_source[source_link_col].astype(str).str.strip()

    df_source_unique = df_source.drop_duplicates(subset=[source_link_col])

    if "content" in df_target.columns:
        df_target = df_target.drop(columns=["content"])
        
    print("Merging content...")
    
    merged_df = pd.merge(
        df_target, 
        df_source_unique[[source_link_col, "Content"]], 
        left_on=target_link_col, 
        right_on=source_link_col, 
        how="left"
    )
    
    if source_link_col in merged_df.columns and source_link_col != target_link_col:
        merged_df = merged_df.drop(columns=[source_link_col])

    if "Content" in merged_df.columns:
        merged_df = merged_df.rename(columns={"Content": "content"})

    merged_df.to_excel(output_file, index=False)
    print(f"Merge completed! Final file saved to: {output_file}")
    
    return output_file