import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from app.auth.authentication import authenticate_user
from app.auth.authorization import (
    can_access_document,
    can_manage_documents,
    can_upload_document,
    can_view_audit_logs,
)
from app.core.pipeline import create_firewall_pipeline
from app.database import feedback as fb
from app.database.audit_log import get_recent_events, log_event
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
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Hallucination Firewall",
    page_icon="🛡️",
    layout="wide",
)

initialize_database()
initialize_registry()
fb.init_tables()

if "user" not in st.session_state:
    st.session_state.user = None

if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0

if "last" not in st.session_state:
    st.session_state.last = None

if "feedback_done" not in st.session_state:
    st.session_state.feedback_done = set()

DOCUMENT_DIRECTORY = Path("data") / "documents"
DOCUMENT_DIRECTORY.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

DEPARTMENTS = [
    "Academic Affairs", "Administration", "College", "General",
    "CSE", "ISE", "ECE", "EEE", "ME", "CE",
]

DOCUMENT_TYPES = [
    "Academic Policy", "Attendance Policy", "Examination Rule",
    "Employee Leave Policy", "Employee Rules", "Student Leave Policy",
    "Department Guideline", "Student Handbook", "Faculty Guideline",
    "Administrative Document",
]

DEFAULT_ROLES = {
    "Employee Leave Policy": ["faculty", "staff"],
    "Employee Rules": ["faculty", "staff"],
    "Faculty Guideline": ["faculty"],
    "Student Leave Policy": ["student"],
    "Student Handbook": ["student", "faculty", "staff"],
}

EXAMPLES = {
    "student": [
        "What is the minimum attendance for semester exams?",
        "Can a student with 72% attendance write the semester exam?",
        "Which experiment covers Docker containers?",
    ],
    "faculty": [
        "What is the employee leave policy?",
        "What should employees do about workplace hazards?",
        "What is the minimum attendance for semester exams?",
    ],
    "staff": [
        "What is the employee leave policy?",
        "How should planned leave be requested?",
        "What should employees do about workplace hazards?",
    ],
    "admin": [
        "What is the minimum attendance for semester exams?",
        "What is the employee leave policy?",
        "Which experiment covers Docker containers?",
    ],
}

CLAIM_BADGES = {
    "supported": ("#16a34a", "Supported"),
    "partially_supported": ("#ea580c", "Partially supported"),
    "contradicted": ("#dc2626", "Contradicted"),
    "unverified": ("#6b7280", "Unverified"),
}

STATUS_BADGES = {
    "VERIFIED": ("#16a34a", "✔ VERIFIED"),
    "PARTIALLY VERIFIED": ("#ea580c", "◐ PARTIALLY VERIFIED"),
    "AMBIGUOUS": ("#ea580c", "? AMBIGUOUS"),
    "ACCESS DENIED": ("#dc2626", "✖ ACCESS DENIED"),
    "BLOCKED": ("#dc2626", "✖ BLOCKED"),
}

# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
    .block-container {max-width: 1100px; padding-top: 1.2rem;}
    header[data-testid="stHeader"] {background: transparent;}

    section[data-testid="stSidebar"] {background: #0b0b10;}
    section[data-testid="stSidebar"] * {color: #e4e4e7 !important;}
    section[data-testid="stSidebar"] .stButton button {
        background: #1f1f2a; border: 1px solid #3f3f46;
    }

    .brand {font-size: 17px; font-weight: 700; margin-bottom: 14px;}
    .brand span {color: #a78bfa;}

    .hero {
        background: #0b0b10; border-radius: 16px; padding: 26px 26px;
        margin-bottom: 18px;
    }
    .hero h1 {color: #ffffff; font-size: 28px; margin: 0 0 6px 0;}
    .hero h1 span {color: #a78bfa;}
    .hero p {color: #a1a1aa; font-size: 15px; margin: 0;}

    .pill {
        display: inline-block; color: #fff; font-weight: 700; font-size: 14px;
        padding: 6px 16px; border-radius: 999px; margin: 6px 0;
    }
    .claim-pill {
        display: inline-block; color: #fff; font-weight: 600; font-size: 12px;
        padding: 2px 10px; border-radius: 999px;
    }
    .doc-row {padding: 10px 4px; border-bottom: 1px solid #ece9f5;}
    .doc-meta {color: #6b6b76; font-size: 13px;}
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #ffffff; border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# HELPERS
# ============================================================


@st.cache_resource(show_spinner="Loading verification models...")
def get_pipeline():
    return create_firewall_pipeline()


def esc(value):
    return html.escape(str(value if value is not None else ""))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def safe_filename(name):
    base = Path(str(name)).name
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(base).stem).strip(" ._")
    extension = Path(base).suffix.lower()

    return (stem or "document")[:100] + extension


def find_duplicate(file_hash):
    for entry in get_all_documents():
        stored = entry.get("file_hash")

        if not stored:
            path = Path(entry.get("file_path") or "")

            if path.is_file():
                stored = sha256_bytes(path.read_bytes())

        if stored == file_hash:
            return entry

    return None


def load_enterprise_documents():
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


def set_query(text):
    st.session_state["query_text"] = text


def require(allowed, message):
    """Server-side page guard: stop rendering if not allowed."""

    if not allowed:
        st.error(message)
        st.stop()


load_default_demo_document()


# ============================================================
# RESULT RENDERING
# ============================================================


def render_banner(status):
    color, label = STATUS_BADGES.get(status, STATUS_BADGES["BLOCKED"])

    st.markdown(
        f'<span class="pill" style="background:{color}">{esc(label)}</span>',
        unsafe_allow_html=True,
    )


def render_citations(result):
    citations = result.get("citations") or []

    if not citations:
        return

    with st.container(border=True):
        st.markdown("**Sources**")

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

    st.markdown("**Evidence**")

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

    st.markdown("**Claim verification**")

    for claim in claims:

        color, label = CLAIM_BADGES.get(
            claim.get("status"), CLAIM_BADGES["unverified"]
        )

        with st.container(border=True):

            st.markdown(
                f'<span class="claim-pill" style="background:{color}">'
                f"{esc(label)}</span>",
                unsafe_allow_html=True,
            )
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


def render_feedback(history_id, user):

    if history_id in st.session_state.feedback_done:
        st.caption("Thanks for your feedback.")
        return

    with st.container(border=True):

        st.markdown("**Was this answer helpful?**")

        comment = st.text_input(
            "Comment (optional)",
            key=f"fbc_{history_id}",
            max_chars=500,
        )

        c1, c2, _ = st.columns([1, 1, 4])

        for column, rating, label in (
            (c1, 1, "👍 Helpful"),
            (c2, -1, "👎 Not helpful"),
        ):
            if column.button(label, key=f"fb_{rating}_{history_id}"):
                if fb.save_feedback(
                    history_id, user["username"], rating, comment
                ):
                    st.session_state.feedback_done.add(history_id)
                    st.rerun()


def render_result(result, user, history_id):
    status = result.get("status", "BLOCKED")

    with st.container(border=True):

        st.markdown("### Answer")
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

    if history_id is not None:
        render_feedback(history_id, user)


# ============================================================
# LOGIN
# ============================================================

if st.session_state.user is None:

    st.markdown(
        '<div class="hero"><h1>🛡️ Hallucination <span>Firewall</span></h1>'
        "<p>Answers you can trust, straight from your college documents. "
        "Every answer is checked, and you only see what your role "
        "allows.</p></div>",
        unsafe_allow_html=True,
    )

    _, middle, _ = st.columns([1, 2, 1])

    with middle:
        with st.container(border=True):

            st.subheader("Welcome back")

            username = st.text_input(
                "Username", placeholder="Enter your username"
            )

            password = st.text_input(
                "Password", type="password",
                placeholder="Enter your password",
            )

            if st.button(
                "Sign in securely", type="primary",
                use_container_width=True,
            ):

                if not username.strip() or not password:
                    st.warning("Please enter both username and password.")

                else:
                    found = authenticate_user(username.strip(), password)

                    if found:
                        st.session_state.user = dict(found)
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

    st.stop()


# ============================================================
# SIDEBAR AND NAVIGATION
# ============================================================

user = st.session_state.user
role = user["role"].lower()

pages = ["Ask", "Documents", "History"]

if can_manage_documents(user):
    pages += ["Review", "Evaluation"]

if can_view_audit_logs(user):
    pages += ["Audit log"]

with st.sidebar:
    st.markdown(
        '<div class="brand">🛡️ Hallucination <span>Firewall</span></div>',
        unsafe_allow_html=True,
    )

    page = st.radio("Navigation", pages, label_visibility="collapsed")

    st.write("")
    st.caption(
        f"{user['full_name']}\n\n"
        f"{user['role'].title()}"
        + (f" • {user['department']}" if user["department"] else "")
    )

    if st.button("Sign out", use_container_width=True):
        st.session_state.user = None
        st.session_state.last = None
        st.rerun()


# ============================================================
# PAGE: ASK
# ============================================================

if page == "Ask":

    st.markdown(
        '<div class="hero"><h1>Ask your college <span>documents</span></h1>'
        "<p>You only see answers from documents your role is allowed to "
        "access.</p></div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):

        st.markdown("### Ask a question")

        query = st.text_area(
            "Ask a question",
            key="query_text",
            placeholder=(
                "Example: Can a 2nd year CSE student with 72% attendance "
                "write the 2026 semester exam?"
            ),
            height=100,
            label_visibility="collapsed",
        )

        st.caption("Try an example:")
        columns = st.columns(3)

        for column, example in zip(columns, EXAMPLES.get(role, [])):
            column.button(
                example,
                key=f"ex_{example}",
                on_click=set_query,
                args=(example,),
                use_container_width=True,
            )

        ask = st.button(
            "🔎 Verify answer", type="primary", use_container_width=True
        )

    if ask:

        if not query.strip():
            st.warning("Please enter a question.")

        else:
            with st.spinner(
                "Searching authorized evidence and verifying the answer..."
            ):
                result = get_pipeline().process_query(
                    user, query, load_enterprise_documents()
                )

            history_id = fb.save_query(
                user["username"],
                query,
                result.get("answer"),
                result.get("status"),
            )

            st.session_state.last = {
                "result": result,
                "history_id": history_id,
            }

    if st.session_state.last:
        render_result(
            st.session_state.last["result"],
            user,
            st.session_state.last["history_id"],
        )


# ============================================================
# PAGE: DOCUMENTS
# ============================================================

elif page == "Documents":

    st.markdown("## 📚 Documents")

    if can_upload_document(user):

        with st.container(border=True):

            st.markdown("### Upload a document")
            st.caption(
                "Uploaded documents are saved as drafts and are not "
                "searchable until an administrator approves them."
            )

            uploaded_file = st.file_uploader(
                "Upload PDF, DOCX or TXT (max 10 MB)",
                type=["pdf", "docx", "txt"],
                key=f"uploader_{st.session_state.upload_key}",
            )

            if uploaded_file is not None:

                c1, c2, c3 = st.columns(3)

                with c1:
                    department = st.selectbox("Department", DEPARTMENTS)

                with c2:
                    document_type = st.selectbox(
                        "Document type", DOCUMENT_TYPES
                    )

                with c3:
                    academic_year = st.number_input(
                        "Academic year", min_value=2020, max_value=2100,
                        value=2026, step=1,
                    )

                c4, c5 = st.columns(2)

                with c4:
                    version = st.text_input("Policy version", value="1.0")

                with c5:
                    effective_date = st.date_input(
                        "Effective date", value=date.today()
                    )

                allowed_roles = st.multiselect(
                    "Who can access this document?",
                    ["student", "faculty", "staff"],
                    default=DEFAULT_ROLES.get(
                        document_type, ["student", "faculty", "staff"]
                    ),
                    key=f"roles_{document_type}",
                )

                if document_type.startswith("Employee"):
                    st.caption(
                        "Tip: employee documents usually use department "
                        "'Administration' so they apply college-wide."
                    )

                if st.button(
                    "⬆️ Add document as draft",
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
                                f"'{duplicate.get('title')}'. "
                                "Nothing was added."
                            )

                        else:
                            name = safe_filename(uploaded_file.name)
                            target = DOCUMENT_DIRECTORY / name

                            if target.exists():
                                target = DOCUMENT_DIRECTORY / (
                                    f"{target.stem}_{file_hash[:8]}"
                                    f"{target.suffix}"
                                )

                            target.write_bytes(data)

                            try:
                                load_document(target)

                            except Exception as error:
                                target.unlink(missing_ok=True)
                                st.error(
                                    "Document could not be processed: "
                                    f"{error}"
                                )

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
                                    f"{target.name} "
                                    f"sha256={file_hash[:12]}",
                                )

                                st.session_state.upload_key += 1
                                st.success(
                                    f"'{uploaded_file.name}' was added "
                                    "as a draft."
                                )
                                st.rerun()

    with st.container(border=True):

        st.markdown("### Documents you can access")

        manager = can_manage_documents(user)

        visible = []

        for document in get_all_documents():
            status = str(document.get("status") or "").lower()
            mine = document.get("owner") == user["username"]

            if manager:
                visible.append(document)
            elif mine or (
                can_access_document(user, document) and status == "official"
            ):
                visible.append(document)

        if not visible:
            st.info("No documents are available to your account.")

        for document in visible:

            status = str(document.get("status") or "unknown").lower()

            st.markdown(
                f'<div class="doc-row"><b>'
                f'{esc(document.get("title", "Unknown document"))}</b>'
                f'<div class="doc-meta">'
                f'{esc(document.get("document_type", ""))} • '
                f'{esc(document.get("department", "Unknown"))} • '
                f'{esc(document.get("academic_year", "N/A"))} • '
                f'Version {esc(document.get("version", "N/A"))} • '
                f"Status: <b>{esc(status)}</b></div></div>",
                unsafe_allow_html=True,
            )

            if manager and status != "official":
                if st.button(
                    "Approve as official",
                    key=f"approve_{document.get('file_path')}",
                ):
                    set_document_status(
                        document.get("file_path"), "official",
                        user["username"],
                    )
                    st.rerun()

            if manager and status == "official":
                if st.button(
                    "Archive",
                    key=f"archive_{document.get('file_path')}",
                ):
                    set_document_status(
                        document.get("file_path"), "archived",
                        user["username"],
                    )
                    st.rerun()


# ============================================================
# PAGE: HISTORY
# ============================================================

elif page == "History":

    st.markdown("## 🕘 Your question history")
    st.caption("Only you can see this list.")

    history = fb.get_history(user["username"], limit=50)

    if not history:
        st.info("You have not asked any questions yet.")

    for item in history:

        color, label = STATUS_BADGES.get(
            item["status"], STATUS_BADGES["BLOCKED"]
        )

        with st.expander(f"{item['question'][:90]}  •  {item['created_at']}"):

            st.markdown(
                f'<span class="claim-pill" style="background:{color}">'
                f"{esc(label)}</span>",
                unsafe_allow_html=True,
            )
            st.write(item["answer"] or "")


# ============================================================
# PAGE: REVIEW (administrators)
# ============================================================

elif page == "Review":

    require(can_manage_documents(user), "Administrators only.")

    st.markdown("## ✅ Review")

    registry = get_all_documents()

    def count(status):
        return sum(
            1 for d in registry
            if str(d.get("status") or "").lower() == status
        )

    summary = fb.get_feedback_summary()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Official documents", count("official"))
    c2.metric("Drafts awaiting review", count("draft"))
    c3.metric("Questions asked", fb.count_queries())
    c4.metric(
        "Feedback 👍 / 👎",
        f"{summary['up']} / {summary['down']}",
    )

    with st.container(border=True):

        st.markdown("### Drafts awaiting approval")

        drafts = [
            d for d in registry
            if str(d.get("status") or "").lower() == "draft"
        ]

        if not drafts:
            st.info("No drafts are waiting.")

        for document in drafts:

            st.write(
                f"**{document.get('title')}** — "
                f"{document.get('document_type')} • "
                f"{document.get('department')} • "
                f"uploaded by {document.get('owner') or 'unknown'}"
            )

            if st.button(
                "Approve as official",
                key=f"rv_approve_{document.get('file_path')}",
            ):
                set_document_status(
                    document.get("file_path"), "official", user["username"]
                )
                st.rerun()

    with st.container(border=True):

        st.markdown("### Recent feedback")

        rows = fb.get_recent_feedback(limit=100)

        if not rows:
            st.info("No feedback yet.")

        else:
            frame = pd.DataFrame(rows)
            frame["rating"] = frame["rating"].map({1: "👍", -1: "👎"})

            st.dataframe(
                frame[
                    ["created_at", "username", "rating", "comment",
                     "status", "question"]
                ],
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# PAGE: EVALUATION (administrators)
# ============================================================

elif page == "Evaluation":

    require(can_manage_documents(user), "Administrators only.")

    st.markdown("## 📊 Evaluation results")

    path = Path("evaluation") / "eval_results.json"

    if not path.exists():
        st.info(
            "No evaluation results yet. Run: "
            "python -m evaluation.run_eval"
        )

    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        summary = data["summary"]

        st.caption(
            f"Dataset {summary['dataset_version']} • "
            f"run on {summary['date']} • "
            f"answer source: {summary['provider']}"
        )

        columns = st.columns(len(summary["by_kind"]))

        for column, (kind, value) in zip(
            columns, summary["by_kind"].items()
        ):
            column.metric(kind.replace("_", " "), value)

        c1, c2 = st.columns(2)
        c1.metric("Unauthorized leaks", summary["leaks"])
        c2.metric("Median latency (ms)", int(summary["median_latency_ms"]))

        st.dataframe(
            pd.DataFrame(data["rows"]),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "This is a small internal test set. Results show how the "
            "system behaves on these questions, not general accuracy."
        )


# ============================================================
# PAGE: AUDIT LOG (administrators)
# ============================================================

elif page == "Audit log":

    require(can_view_audit_logs(user), "Administrators only.")

    st.markdown("## 🧾 Audit log")

    events = get_recent_events(limit=300)

    if not events:
        st.info("No events recorded yet.")

    else:
        frame = pd.DataFrame(events)

        kinds = ["all"] + sorted(frame["event_type"].unique().tolist())
        chosen = st.selectbox("Event type", kinds)

        if chosen != "all":
            frame = frame[frame["event_type"] == chosen]

        st.dataframe(frame, use_container_width=True, hide_index=True)