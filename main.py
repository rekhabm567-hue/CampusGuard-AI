import hashlib
import re
from datetime import date
from pathlib import Path

import streamlit as st

from app.auth.authentication import authenticate_user
from app.auth.authorization import (
    can_access_document,
    can_manage_documents,
    can_upload_document,
)
from app.core.pipeline import create_firewall_pipeline
from app.database.audit_log import log_event
from app.database.database import initialize_database
from app.documents.chunker import create_document_chunks
from app.documents.loader import load_document
from app.documents.metadata import create_metadata
from app.documents.registry import (
    add_document_metadata,
    get_all_documents,
    initialize_registry,
    load_registry,
    save_registry,
)

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="LLM Hallucination Firewall",
    page_icon="🛡️",
    layout="wide",
)

initialize_database()
initialize_registry()

if "user" not in st.session_state:
    st.session_state.user = None

if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0

DOCUMENT_DIRECTORY = Path("data") / "documents"
DOCUMENT_DIRECTORY.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

CLAIM_BADGES = {
    "supported": ("🟢", "Supported"),
    "partially_supported": ("🟡", "Partially supported"),
    "contradicted": ("🔴", "Contradicted"),
    "unverified": ("⚪", "Unverified"),
}


# ============================================================
# HELPERS
# ============================================================

@st.cache_resource(show_spinner="Loading verification models...")
def get_pipeline():
    return create_firewall_pipeline()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def safe_filename(name):
    base = Path(str(name)).name
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(base).stem).strip(" ._")
    extension = Path(base).suffix.lower()

    return (stem or "document")[:100] + extension


def find_duplicate(file_hash):
    """Return the registry entry whose file has the same hash, or None."""

    for entry in get_all_documents():
        stored = entry.get("file_hash")

        if not stored:
            path = Path(entry.get("file_path") or "")

            if path.is_file():
                stored = sha256_file(path)

        if stored == file_hash:
            return entry

    return None


def load_enterprise_documents():
    """All registered documents as chunks (authorization happens later)."""

    documents = []

    for metadata in get_all_documents():

        file_path = metadata.get("file_path")

        if not file_path or not Path(file_path).exists():
            continue

        try:
            chunks = create_document_chunks(load_document(file_path))
        except Exception:
            continue

        for chunk in chunks:
            documents.append({**chunk, **metadata})

    return documents


def load_default_demo_document():

    demo_path = DOCUMENT_DIRECTORY / "attendance_policy_2026.txt"

    if not demo_path.exists():
        return

    if any(
        item.get("file_path") == str(demo_path)
        for item in get_all_documents()
    ):
        return

    metadata = create_metadata(
        title="2026 Academic Attendance Policy",
        department="Academic Affairs",
        document_type="Attendance Policy",
        academic_year=2026,
        version="2.0",
        effective_date="2026-06-01",
        allowed_roles=["student", "faculty", "staff"],
        file_path=str(demo_path),
        status="official",
    )

    add_document_metadata(metadata.to_dict())


def set_document_status(file_path, status, username):

    documents = load_registry()

    for document in documents:
        if document.get("file_path") == file_path:
            document["status"] = status

    save_registry(documents)
    log_event("document_status", username, f"{file_path} -> {status}")


load_default_demo_document()


# ============================================================
# RESULT RENDERING
# ============================================================

def render_banner(status):

    if status == "VERIFIED":
        st.success("🟢 VERIFIED")
    elif status == "PARTIALLY VERIFIED":
        st.warning("🟡 PARTIALLY VERIFIED")
    elif status == "AMBIGUOUS":
        st.warning("🟠 AMBIGUOUS")
    elif status == "ACCESS DENIED":
        st.error("🔴 ACCESS DENIED")
    else:
        st.error("🔴 BLOCKED")


def render_citations(result):

    citations = result.get("citations") or []

    if not citations:
        return

    st.subheader("Sources")

    for number, citation in enumerate(citations, start=1):

        parts = [citation.get("title") or "Unknown document"]

        if citation.get("version"):
            parts.append(f"Version {citation['version']}")

        if citation.get("page") is not None:
            parts.append(f"Page {citation['page']}")

        label = " • ".join(str(p) for p in parts)

        if citation.get("attached_by") == "system":
            label += " (attached by the system from verified evidence)"

        st.write(f"**[{number}]** {label}")


def render_evidence(result):

    evidence = result.get("evidence") or []

    if not evidence:
        return

    st.subheader("Evidence")

    for index, item in enumerate(evidence, start=1):

        title = item.get("title") or item.get("file_name") or "Unknown"

        with st.expander(f"Evidence {index} — {title}"):

            st.write(item.get("text", ""))

            details = [
                f"Version: {item.get('version', 'N/A')}",
                f"Academic Year: {item.get('academic_year', 'N/A')}",
                f"Effective Date: {item.get('effective_date', 'N/A')}",
            ]

            if item.get("page") is not None:
                details.append(f"Page: {item['page']}")

            st.caption(" • ".join(details))


def render_claims(result):

    claims = result.get("claims") or []

    if not claims:
        return

    st.subheader("Claim Verification")

    for claim in claims:

        icon, label = CLAIM_BADGES.get(
            claim.get("status"), ("⚪", "Unverified")
        )

        st.markdown(f"{icon} **{label}**")
        st.write(claim.get("claim", ""))

        notes = list(claim.get("reasons") or [])

        if claim.get("method") and claim["method"] != "none":
            notes.append(f"Method: {claim['method']}")

        if notes:
            st.caption(" ".join(notes))

        for ref in (claim.get("contradicting") or [])[:2]:
            st.caption(
                f"Conflicts with: {ref.get('title')} — "
                f"“{ref.get('excerpt', '')}”"
            )


def render_result(result, user):

    status = result.get("status", "BLOCKED")

    st.subheader("Answer")
    st.write(result.get("answer", "No answer available."))

    render_banner(status)

    st.write(f"**Verification:** {result.get('reason', '')}")

    meta = []

    if result.get("provider"):
        meta.append(f"Answer source: {result['provider']}")

    if result.get("reranker"):
        meta.append(f"Reranker: {result['reranker']}")

    if "nli_used" in result:
        meta.append(
            "Entailment model: "
            + ("on" if result["nli_used"] else "off")
        )

    if result.get("latency_ms") is not None:
        meta.append(f"{result['latency_ms']} ms")

    if meta:
        st.caption(" • ".join(meta))

    render_citations(result)
    render_evidence(result)
    render_claims(result)

    if (
        result.get("rejected_answer")
        and user["role"].lower() == "admin"
    ):
        with st.expander("Withheld draft answer (admin only)"):
            st.write(result["rejected_answer"])


# ============================================================
# LOGIN PAGE
# ============================================================

st.markdown(
    "<h1 style='text-align:center'>🛡️ LLM Hallucination Firewall</h1>"
    "<p style='text-align:center'>Secure Enterprise Knowledge "
    "Verification</p>",
    unsafe_allow_html=True,
)

if st.session_state.user is None:

    with st.container(border=True):

        st.subheader("Secure Sign In")
        st.write("Sign in to access the enterprise knowledge system.")

        username = st.text_input(
            "Username", placeholder="Enter your username"
        )

        password = st.text_input(
            "Password", type="password", placeholder="Enter your password"
        )

        if st.button("Sign in securely", use_container_width=True):

            if not username.strip() or not password:
                st.warning("Please enter both username and password.")

            else:
                user = authenticate_user(username.strip(), password)

                if user:
                    st.session_state.user = dict(user)
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    st.stop()


# ============================================================
# MAIN APPLICATION
# ============================================================

user = st.session_state.user

col_a, col_b = st.columns([4, 1])

with col_a:
    st.write(f"Welcome, **{user['full_name']}**")
    st.caption(
        f"Role: {user['role'].title()}"
        + (f" • Department: {user['department']}" if user["department"] else "")
    )

with col_b:
    if st.button("Sign out", use_container_width=True):
        st.session_state.user = None
        st.rerun()

st.divider()


# ------------------------------------------------------------
# DOCUMENT UPLOAD
# ------------------------------------------------------------

st.subheader("📄 Enterprise Document Management")

if can_upload_document(user):

    st.caption(
        "Uploaded documents are saved as drafts and are not searchable "
        "until an administrator approves them."
    )

    uploaded_file = st.file_uploader(
        "Upload PDF, DOCX or TXT (max 10 MB)",
        type=["pdf", "docx", "txt"],
        key=f"uploader_{st.session_state.upload_key}",
    )

    if uploaded_file is not None:

        c1, c2, c3 = st.columns(3)

        with c1:
            department = st.selectbox(
                "Department",
                [
                    "Academic Affairs", "CSE", "ISE", "ECE", "EEE", "ME",
                    "CE", "Administration", "College", "General",
                ],
            )

        with c2:
            document_type = st.selectbox(
                "Document Type",
                [
                    "Academic Policy", "Attendance Policy",
                    "Examination Rule", "Leave Policy",
                    "Department Guideline", "Student Handbook",
                    "Faculty Guideline", "Administrative Document",
                ],
            )

        with c3:
            academic_year = st.number_input(
                "Academic Year", min_value=2020, max_value=2100,
                value=2026, step=1,
            )

        c4, c5 = st.columns(2)

        with c4:
            version = st.text_input("Policy Version", value="1.0")

        with c5:
            effective_date = st.date_input(
                "Effective Date", value=date.today()
            )

        allowed_roles = st.multiselect(
            "Who can access this document?",
            ["student", "faculty", "staff"],
            default=["student", "faculty", "staff"],
        )

        if st.button(
            "⬆️ Add Document as Draft",
            type="primary",
            use_container_width=True,
        ):

            data = uploaded_file.getvalue()
            extension = Path(uploaded_file.name).suffix.lower()

            if extension not in ALLOWED_EXTENSIONS:
                st.error("Unsupported file type.")

            elif len(data) > MAX_UPLOAD_BYTES:
                st.error("File is larger than 10 MB.")

            elif not data:
                st.error("The file is empty.")

            elif not allowed_roles:
                st.error("Choose at least one role.")

            else:
                file_hash = sha256_bytes(data)
                duplicate = find_duplicate(file_hash)

                if duplicate:
                    st.warning(
                        "This file is already registered as "
                        f"'{duplicate.get('title')}'. Nothing was added."
                    )

                else:
                    name = safe_filename(uploaded_file.name)
                    target = DOCUMENT_DIRECTORY / name

                    if target.exists():
                        target = DOCUMENT_DIRECTORY / (
                            f"{target.stem}_{file_hash[:8]}{target.suffix}"
                        )

                    target.write_bytes(data)

                    try:
                        load_document(target)

                    except Exception as error:
                        target.unlink(missing_ok=True)
                        st.error(f"Document could not be processed: {error}")

                    else:
                        metadata = create_metadata(
                            title=uploaded_file.name,
                            department=department,
                            document_type=document_type,
                            academic_year=int(academic_year),
                            version=version,
                            effective_date=str(effective_date),
                            allowed_roles=allowed_roles,
                            file_path=str(target),
                            status="draft",
                            owner=user["username"],
                        ).to_dict()

                        metadata["file_hash"] = file_hash

                        add_document_metadata(metadata)

                        log_event(
                            "document_upload",
                            user["username"],
                            f"{target.name} sha256={file_hash[:12]}",
                        )

                        st.session_state.upload_key += 1
                        st.success(
                            f"'{uploaded_file.name}' was added as a draft."
                        )
                        st.rerun()

else:
    st.caption("Only Admin and Faculty users can upload documents.")


# ------------------------------------------------------------
# DOCUMENT LIST
# ------------------------------------------------------------

st.subheader("📚 Registered Enterprise Documents")

visible = [
    document
    for document in get_all_documents()
    if can_access_document(user, document)
    or document.get("owner") == user["username"]
]

if not visible:
    st.info("No documents are available to your account.")

for document in visible:

    status = str(document.get("status") or "unknown").lower()

    st.write(
        f"📄 **{document.get('title', 'Unknown document')}** • "
        f"{document.get('department', 'Unknown')} • "
        f"{document.get('academic_year', 'N/A')} • "
        f"Version {document.get('version', 'N/A')} • "
        f"Status: **{status}**"
    )

    if can_manage_documents(user) and status != "official":
        if st.button(
            "Approve as official",
            key=f"approve_{document.get('file_path')}",
        ):
            set_document_status(
                document.get("file_path"), "official", user["username"]
            )
            st.rerun()

    if can_manage_documents(user) and status == "official":
        if st.button(
            "Archive",
            key=f"archive_{document.get('file_path')}",
        ):
            set_document_status(
                document.get("file_path"), "archived", user["username"]
            )
            st.rerun()

st.divider()


# ------------------------------------------------------------
# KNOWLEDGE SEARCH
# ------------------------------------------------------------

st.subheader("Ask the Enterprise Knowledge System")

query = st.text_area(
    "Ask a question",
    placeholder=(
        "Example: Can a 2nd year CSE student with 72% attendance "
        "write the 2026 semester exam?"
    ),
    height=100,
    label_visibility="collapsed",
)

if st.button("🔎 Verify Answer", type="primary", use_container_width=True):

    if not query.strip():
        st.warning("Please enter a question.")

    else:
        with st.spinner(
            "Searching authorized evidence and verifying the answer..."
        ):
            result = get_pipeline().process_query(
                user, query, load_enterprise_documents()
            )

        render_result(result, user)