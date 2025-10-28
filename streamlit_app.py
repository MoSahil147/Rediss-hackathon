import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="Invoice AI Processor", page_icon="🧾", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
        body { background-color: #0a0a0a; }
        .stApp { background-color: #0a0a0a; color: #fff; }
        .uploadbox { border: 2px dashed #ef4444; background: #1a1a1a; border-radius: 16px; }
        .stButton>button { background-color: #ef4444 !important; color: #fff !important; border-radius: 8px; border: none; }
        .jsonbox { background: #1a1a1a; border-radius: 12px; border: 2px solid #ef4444; padding: 16px; color: #e5e5e5; font-size: 1.08em; }
        .redbadge { background: #ef4444; color: #fff; padding: 3px 8px; border-radius: 6px; }
        .progress-ring { display: flex; align-items: center; justify-content: center; }
    </style>
""", unsafe_allow_html=True)

st.title("🧾 AI Invoice Processing System")
st.markdown('<span style="color:#ef4444; font-weight:bold; font-size:18px;">Black & Red Theme | Streamlit</span>', unsafe_allow_html=True)
st.write("Upload an invoice PDF to extract key fields using the AI backend.")

backend_url = "http://localhost:8080/process-pdf-upload-redis"

uploaded_file = st.file_uploader("Drop PDF here or click to browse", type="pdf", label_visibility="visible")

if uploaded_file:
    st.markdown(
        f'<div class="uploadbox"><span class="redbadge">{uploaded_file.name}</span> &nbsp; Size: {uploaded_file.size / 1024:.2f} KB</div>',
        unsafe_allow_html=True,
    )
    if uploaded_file.size > 10 * 1024 * 1024:
        st.error("File too large. Max 10 MB allowed.")
    else:
        if st.button("Upload & Process Invoice", key="process_btn"):
            with st.spinner("⚡ Processing document with AI..."):
                progress_bar = st.progress(0)
                stages = [
                    "Uploading document...",
                    "Extracting text...",
                    "AI Processing...",
                    "Generating results..."
                ]
                for i, stage in enumerate(stages):
                    st.write(f"**Stage {i+1}: {stage}**")
                    progress_bar.progress((i+1)*25)
                    time.sleep(0.6)
                try:
                    response = requests.post(
                        backend_url,
                        files={"file": (uploaded_file.name, uploaded_file, "application/pdf")},
                        timeout=60
                    )
                    if response.status_code == 200:
                        st.success("✅ Extraction Complete!")
                        result_json = response.json()
                        st.markdown('<div class="jsonbox">', unsafe_allow_html=True)
                        st.code(json.dumps(result_json, indent=2), language="json")
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.download_button("Download JSON", data=json.dumps(result_json, indent=2), file_name="invoice_result.json")
                    else:
                        st.error(f"API Error: {response.status_code}\n{response.text}")
                except Exception as e:
                    st.error(f"Error during request: {e}")

        st.button("Reset", on_click=lambda: st.rerun())

st.markdown("---")
st.caption("Powered by FastAPI & Streamlit | Black & Red Theme | v1.0")

