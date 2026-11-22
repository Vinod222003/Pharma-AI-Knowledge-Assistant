import requests
import streamlit as st

st.set_page_config(page_title="Pharma AI Assistant", page_icon="🧪", layout="wide")
st.title("🧪 Enterprise AI Regulatory & Medical Knowledge Assistant")
st.warning("Educational capstone only. Not validated for GxP, patient care, batch release, regulatory submissions, or operational decisions.")
API = st.sidebar.text_input("API URL", "http://127.0.0.1:8000").rstrip("/")

def call(method, path, **kwargs):
    headers = {"Authorization": "Bearer " + st.session_state.token} if st.session_state.get("token") else {}
    response = requests.request(method, API + path, headers=headers, timeout=180, **kwargs)
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(f"HTTP {response.status_code}: {detail}")
    return response.json()

if "token" not in st.session_state:
    st.session_state.token = ""
if not st.session_state.token:
    st.subheader("Sign in")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign in")
    if submit:
        try:
            data = call("POST", "/api/auth/login", json={"username": username, "password": password})
            st.session_state.token = data["access_token"]
            st.session_state.identity = data
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.stop()

identity = st.session_state.get("identity", {})
st.sidebar.success(f"Signed in: {identity.get('username', '')} ({identity.get('role', '')})")
if st.sidebar.button("Sign out"):
    st.session_state.token = ""
    st.session_state.identity = {}
    st.rerun()

role = identity.get("role", "viewer")
my_dept = identity.get("department", "general")
options = ["general", "quality", "regulatory", "medical"] if role == "admin" else sorted({"general", my_dept})
tabs = st.tabs(["Overview", "Ask AI", "Upload", "Documents", "Audit / Users"])

with tabs[0]:
    st.subheader("Document overview")
    try:
        docs = call("GET", "/api/documents")
        c1, c2, c3 = st.columns(3)
        c1.metric("Accessible versions", len(docs))
        c2.metric("Active documents", sum(x["status"] == "active" for x in docs))
        c3.metric("Superseded versions", sum(x["status"] == "superseded" for x in docs))
    except Exception as exc:
        st.error(str(exc))

with tabs[1]:
    question = st.text_area("Ask a question supported by your indexed documents", height=110)
    department = st.selectbox("Department", ["All accessible"] + options)
    if st.button("Ask assistant", type="primary"):
        if not question.strip():
            st.warning("Enter a question first")
        else:
            try:
                result = call("POST", "/api/ask", json={"question": question,
                              "department": None if department == "All accessible" else department})
                st.markdown("### Answer")
                st.write(result["answer"])
                st.markdown("### Cited evidence")
                for src in result.get("sources", []):
                    with st.expander(f"[{src['label']}] {src['filename']} — page {src['page']}"):
                        st.write(src["excerpt"])
                if result.get("insufficient_evidence"):
                    st.info("No sufficiently supported answer was available")
            except Exception as exc:
                st.error(str(exc))

with tabs[2]:
    if role == "viewer":
        st.info("Viewer accounts cannot upload documents")
    else:
        upload = st.file_uploader("Choose a document", type=["pdf", "docx", "txt", "csv", "xlsx", "xls"])
        dept = st.selectbox("Document department", options)
        doc_type = st.selectbox("Document type", ["SOP", "Guideline", "BMR", "QC Report", "CAPA", "Deviation", "Other"])
        if st.button("Upload and index", disabled=upload is None):
            try:
                response = call("POST", "/api/documents/upload", params={"department": dept, "doc_type": doc_type},
                                files={"file": (upload.name, upload.getvalue(), upload.type or "application/octet-stream")})
                st.success(response)
            except Exception as exc:
                st.error(str(exc))

with tabs[3]:
    if st.button("Refresh document library"):
        st.rerun()
    try:
        docs = call("GET", "/api/documents")
        st.dataframe(docs, use_container_width=True, hide_index=True)
        st.caption("Rows with the same filename and department show document version history. Only active versions are searchable.")
    except Exception as exc:
        st.error(str(exc))

with tabs[4]:
    if role != "admin":
        st.info("Administrator access required")
    else:
        try:
            st.subheader("Recent audit events")
            st.dataframe(call("GET", "/api/audit"), use_container_width=True, hide_index=True)
            st.subheader("Users")
            st.dataframe(call("GET", "/api/users"), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(str(exc))
        with st.form("new_user"):
            st.markdown("**Create user**")
            new_username = st.text_input("New username")
            new_password = st.text_input("Temporary password (12+ characters)", type="password")
            new_department = st.selectbox("New user department", ["general", "quality", "medical", "regulatory"])
            new_role = st.selectbox("New user role", ["viewer", "quality", "medical", "regulatory", "admin"])
            create = st.form_submit_button("Create user")
        if create:
            try:
                st.success(call("POST", "/api/users", json={"username": new_username,
                    "password": new_password, "role": new_role, "department": new_department}))
            except Exception as exc:
                st.error(str(exc))
