import os
import pandas as pd

def merge_link_content(target_file, source_file="LinkContent.xlsx", output_file="final_output.xlsx"):
    """
    Merge the target file with the source file based on the URL.
    Adds the 'content' column to the target file.
    """
    print(f"Reading target file: {target_file} and source file: {source_file}...")
    
    if not os.path.exists(target_file):
        raise FileNotFoundError(f"Target file not found: {target_file}")
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Source file not found: {source_file}")
        
    df_target = pd.read_excel(target_file)
    df_source = pd.read_excel(source_file)
    
    # Define column names
    target_link_col = "Link_URL"
    source_link_col = "URL"
    
    if target_link_col not in df_target.columns:
        raise ValueError(f"Error: Column '{target_link_col}' not found in target file.")
    if source_link_col not in df_source.columns:
        raise ValueError(f"Error: Column '{source_link_col}' not found in source file.")

    # Clean the URLs by removing leading and trailing whitespaces to ensure accurate matching
    df_target[target_link_col] = df_target[target_link_col].astype(str).str.strip()
    df_source[source_link_col] = df_source[source_link_col].astype(str).str.strip()

    # Remove duplicates from the source file based on the URL
    df_source_unique = df_source.drop_duplicates(subset=[source_link_col])

    # If the target file already has a 'content' column, drop it to avoid conflicts
    if "content" in df_target.columns:
        df_target = df_target.drop(columns=["content"])
        
    print("Merging content...")
    
    # Perform a left join
    merged_df = pd.merge(
        df_target, 
        df_source_unique[[source_link_col, "Content"]], 
        left_on=target_link_col, 
        right_on=source_link_col, 
        how="left"
    )
    
    # Drop the redundant URL column from the source file if it exists
    if source_link_col in merged_df.columns and source_link_col != target_link_col:
        merged_df = merged_df.drop(columns=[source_link_col])

    # Standardize the new column name to lowercase 'content'
    if "Content" in merged_df.columns:
        merged_df = merged_df.rename(columns={"Content": "content"})

    # Save the final output
    merged_df.to_excel(output_file, index=False)
    print(f"Merge completed! Final file saved to: {output_file}")
    
    return output_file

if __name__ == "__main__":
    import sys
    
    # Get parameters from the terminal, or use defaults if not provided
    target_f = sys.argv[1] 
    source_f = sys.argv[2] 
    output_f = sys.argv[3] if len(sys.argv) > 3 else "merged_data.xlsx"    

    # Execute the function
    merge_link_content(
        target_file=target_f,
        source_file=source_f,
        output_file=output_f
    )
