import os
import time
import pandas as pd
import streamlit as st
from ai_verifier import run_ai_verification

@st.cache_resource
def get_step4_registry():
    return {}

def _step4_worker(sid, input_file_path, prompt, config, checkpoint_path, job):
    try:
        df_all = pd.read_excel(input_file_path)
        total = len(df_all)

        if os.path.exists(checkpoint_path):
            df_done = pd.read_excel(checkpoint_path)
        else:
            df_done = pd.DataFrame()

        start_idx = len(df_done)

        with job['lock']:
            job['total'] = total
            job['done'] = start_idx

        chunk_size = 10
        chunk_input_path = f"{sid}_step4_chunk_input_tmp.xlsx"
        chunk_output_path = f"{sid}_step4_chunk_output_tmp.xlsx"

        def chunk_cb(message, is_detail=False):
            with job['lock']:
                job['logs'].append(message)
                job['logs'] = job['logs'][-30:]

        idx = start_idx
        while idx < total:
            end_idx = min(idx + chunk_size, total)
            df_chunk = df_all.iloc[idx:end_idx].reset_index(drop=True)
            df_chunk.to_excel(chunk_input_path, index=False)

            run_ai_verification(
                input_file=chunk_input_path,
                output_file=chunk_output_path,
                prompt=prompt,
                provider=config["LLM_PROVIDER"],
                api_key=config["LLM_API_KEY"],
                base_url=config["LLM_BASE_URL"],
                model_name=config["LLM_MODEL"],
                progress_callback=chunk_cb
            )

            df_chunk_result = pd.read_excel(chunk_output_path)
            df_done = pd.concat([df_done, df_chunk_result], ignore_index=True)
            df_done.to_excel(checkpoint_path, index=False)

            idx = end_idx
            with job['lock']:
                job['done'] = idx
                job['last_update'] = time.time()

        with job['lock']:
            job['finished'] = True
            job['error'] = None

    except Exception as e:
        with job['lock']:
            job['error'] = str(e)
            job['finished'] = True