import os
import requests
import streamlit as st

st.set_page_config(page_title="Pharma AI Assistant", page_icon="🧪", layout="wide")
st.title("🧪 Enterprise AI Regulatory & Medical Knowledge Assistant")
st.warning("Educational capstone only. Not validated for GxP, patient care, batch release, regulatory submissions, or operational decisions.")
API = st.sidebar.text_input("API URL", os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")).rstrip("/")

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
tabs = st.tabs(["Overview", "Ask AI", "Upload", "Documents", "Audit / Users", "SOP Intelligence", "Evaluation & Reports"])

with tabs[0]:
    st.subheader("Document overview")
    try:
        docs = call("GET", "/api/documents")
        c1, c2, c3 = st.columns(3)
        c1.metric("Accessible versions", len(docs))
        c2.metric("Active documents", sum(x["status"] == "active" for x in docs))
        c3.metric("Superseded versions", sum(x["status"] == "superseded" for x in docs))
        analytics = call("GET", "/api/analytics")
        a, b = st.columns(2)
        with a:
            st.markdown("**Active documents by department**")
            st.bar_chart(analytics.get("by_department", {}))
        with b:
            st.markdown("**Active documents by type**")
            st.bar_chart(analytics.get("by_type", {}))
        if role == "admin" and analytics.get("audit_action_counts"):
            st.markdown("**Audited activity**")
            st.bar_chart(analytics["audit_action_counts"])
    except Exception as exc:
        st.error(str(exc))

with tabs[1]:
    question = st.text_area("Ask a question supported by your indexed documents", height=110)
    department = st.selectbox("Department", ["All accessible"] + options)
    agent = st.selectbox("AI agent", ["auto", "quality_agent", "regulatory_agent", "document_agent"])
    if st.button("Ask assistant", type="primary"):
        if not question.strip():
            st.warning("Enter a question first")
        else:
            try:
                result = call("POST", "/api/agents/ask", json={"question": question,
                              "agent": agent, "department": None if department == "All accessible" else department})
                st.session_state.last_question = question
                st.session_state.last_department = None if department == "All accessible" else department
                st.session_state.last_agent = agent
                st.markdown("### Answer")
                st.caption("Agent: " + result.get("agent", agent))
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
        st.dataframe(docs, width="stretch", hide_index=True)
        st.caption("Rows with the same filename and department show document version history. Only active versions are searchable.")
    except Exception as exc:
        st.error(str(exc))

with tabs[4]:
    if role != "admin":
        st.info("Administrator access required")
    else:
        try:
            st.subheader("Recent audit events")
            st.dataframe(call("GET", "/api/audit"), width="stretch", hide_index=True)
            st.subheader("Users")
            st.dataframe(call("GET", "/api/users"), width="stretch", hide_index=True)
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


with tabs[5]:
    st.subheader("SOP version comparison")
    st.caption("Compare two uploaded versions of the same SOP, subject to your document permissions.")
    try:
        library = call("GET", "/api/documents")
        choices = {f"{x['id']} — {x['filename']} (v{x['version']}, {x['department']})": x['id'] for x in library}
        if len(choices) >= 2:
            left, right = st.columns(2)
            with left:
                first = st.selectbox("Original document", list(choices), key="compare_first")
            with right:
                second = st.selectbox("Updated document", list(choices), index=min(1, len(choices)-1), key="compare_second")
            if st.button("Compare versions"):
                out = call("GET", "/api/documents/compare", params={"first_id": choices[first], "second_id": choices[second]})
                st.success("Change detected" if out['changed'] else "No textual difference")
                st.code("\n".join(out['diff_lines']) or "No changes", language="diff")
                st.caption(out['note'])
        else:
            st.info("Upload two versions of the same document to compare them.")
    except Exception as exc:
        st.error(str(exc))
    st.divider()
    st.subheader("Evidence-based checklist gap scan")
    st.caption("This checks potential lexical evidence, not real-world GMP compliance.")
    checklist = st.text_area("Separate checklist requirements using commas or semicolons", key="gap_text", placeholder="batch manufacturing record; certificate of analysis; environmental monitoring logs")
    gap_department = st.selectbox("Checklist department", options, key="gap_department")
    if st.button("Scan evidence", disabled=not checklist.strip()):
        try:
            gap = call("POST", "/api/compliance/gap-check", json={"checklist": checklist, "department": gap_department})
            st.metric("Items with possible matching evidence", f"{gap['with_potential_evidence']} / {gap['total_checks']}")
            st.dataframe([{"requirement": item['requirement'], "evidence_found": item['evidence_found'],
                           "sources": ", ".join(s['filename'] for s in item['sources'])} for item in gap['checks']], width="stretch", hide_index=True)
            st.warning(gap['disclaimer'])
        except Exception as exc:
            st.error(str(exc))

with tabs[6]:
    st.subheader("RAG response evaluation")
    st.caption("Simple citation/reference checks, not validated faithfulness or clinical accuracy measurements.")
    eval_question = st.text_area("Evaluation question", value="What are the mandatory batch release checklist requirements in SOP-002?", key="eval_question")
    eval_department = st.selectbox("Evaluation department", options, key="eval_department")
    if st.button("Evaluate response"):
        try:
            payload = call("POST", "/api/evaluation/case", json={"question": eval_question, "department": eval_department, "agent": "auto"})
            st.json(payload['metrics'])
            st.write(payload['result']['answer'])
        except Exception as exc:
            st.error(str(exc))
    st.divider()
    st.subheader("Download evidence-referenced PDF")
    report_question = st.text_area("Report question", value=st.session_state.get('last_question', ''), key="report_question")
    report_dept = st.selectbox("Report department", options, key="report_department")
    if st.button("Generate PDF report", disabled=not report_question.strip()):
        try:
            response = requests.post(API + "/api/reports/answer.pdf",
                headers={"Authorization": "Bearer " + st.session_state.token},
                json={"question": report_question, "department": report_dept, "title": "Pharma AI Evidence Report", "agent": "auto"}, timeout=180)
            response.raise_for_status()
            st.session_state.generated_report = response.content
        except Exception as exc:
            st.error(str(exc))
    if st.session_state.get('generated_report'):
        st.download_button("Download PDF", data=st.session_state.generated_report,
                           file_name="pharma_evidence_report.pdf", mime="application/pdf")
