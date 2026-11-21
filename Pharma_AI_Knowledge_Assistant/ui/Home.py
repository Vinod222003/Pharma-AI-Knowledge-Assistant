import streamlit as st
import requests

st.set_page_config(page_title="Pharma AI Knowledge Assistant", page_icon="🧪", layout="wide")
st.title("🧪 Enterprise AI Regulatory & Medical Knowledge Assistant")
st.caption("Educational capstone demo — verify every answer against approved controlled documents.")
API = st.sidebar.text_input("API URL", "http://127.0.0.1:8000")
tab1, tab2, tab3 = st.tabs(["Ask the assistant", "Upload documents", "Document library"])

with tab1:
    question = st.text_area("Ask a question about your indexed documents", height=120,
        placeholder="Example: What does the uploaded demo procedure say about recording a deviation?")
    dept = st.selectbox("Department filter", ["", "regulatory", "medical", "quality", "general"])
    if st.button("Ask", type="primary"):
        try:
            r = requests.post(f"{API}/api/ask", json={"question": question, "department": dept or None}, timeout=120)
            r.raise_for_status()
            data = r.json()
            st.markdown("### Answer")
            st.write(data["answer"])
            st.markdown("### Retrieved sources")
            for src in data.get("sources", []):
                with st.expander(f'{src.get("filename")} — page {src.get("page")}'):
                    st.write(src.get("excerpt"))
        except Exception as e:
            st.error(f"Could not reach the API: {e}")

with tab2:
    up = st.file_uploader("Choose PDF, DOCX, TXT, CSV or XLSX", type=["pdf","docx","txt","csv","xlsx"])
    department = st.selectbox("Document department", ["general","regulatory","medical","quality"], key="updept")
    doc_type = st.selectbox("Document type", ["SOP","Guideline","BMR","QC Report","CAPA","Deviation","Other"])
    if st.button("Upload and index", disabled=up is None):
        try:
            r = requests.post(f"{API}/api/documents/upload", params={"department":department,"doc_type":doc_type},
                files={"file": (up.name, up.getvalue(), up.type or "application/octet-stream")}, timeout=180)
            r.raise_for_status()
            st.success(r.json())
        except Exception as e:
            st.error(f"Upload failed: {e}")

with tab3:
    if st.button("Refresh library"):
        try:
            r = requests.get(f"{API}/api/documents", timeout=20); r.raise_for_status()
            st.dataframe(r.json(), use_container_width=True)
        except Exception as e:
            st.error(f"Could not load documents: {e}")

st.divider()
st.warning("Demo only. Do not use for patient care, batch release, regulatory submissions, or operational decisions without formal validation and authorized review.")
