import streamlit as st
from pathlib import Path

from app.auth.authentication import authenticate_user
from app.database.database import initialize_database

from app.core.pipeline import create_firewall_pipeline

from app.documents.loader import load_document
from app.documents.chunker import create_document_chunks
from app.documents.metadata import create_metadata

from app.documents.registry import (
    initialize_registry,
    add_document_metadata,
    get_all_documents,
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="LLM Hallucination Firewall",
    page_icon="🛡️",
    layout="wide",
)


# ============================================================
# INITIALIZATION
# ============================================================

initialize_database()
initialize_registry()

if "user" not in st.session_state:
    st.session_state.user = None


# ============================================================
# DOCUMENT STORAGE
# ============================================================

DOCUMENT_DIRECTORY = Path(
    "data"
) / "documents"

DOCUMENT_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD REGISTERED DOCUMENTS
# ============================================================

def load_enterprise_documents():

    documents = []

    registered_documents = get_all_documents()

    for metadata in registered_documents:

        file_path = metadata.get(
            "file_path"
        )

        if not file_path:
            continue

        path = Path(file_path)

        if not path.exists():
            continue

        try:

            document = load_document(
                file_path
            )

            chunks = create_document_chunks(
                document
            )

            for chunk in chunks:

                documents.append(
                    {
                        **chunk,
                        **metadata,
                    }
                )

        except Exception:
            continue

    return documents


# ============================================================
# LOAD DEFAULT DEMO POLICY
# ============================================================

def load_default_demo_document():

    demo_path = (
        DOCUMENT_DIRECTORY
        / "attendance_policy_2026.txt"
    )

    if not demo_path.exists():
        return

    registered_documents = get_all_documents()

    already_registered = any(
        item.get("file_path")
        == str(demo_path)
        for item in registered_documents
    )

    if already_registered:
        return

    metadata = create_metadata(
        title="2026 Academic Attendance Policy",
        department="Academic Affairs",
        document_type="Attendance Policy",
        academic_year=2026,
        version="2.0",
        effective_date="2026-06-01",
        allowed_roles=[
            "student",
            "faculty",
            "staff",
        ],
        file_path=str(demo_path),
    )

    add_document_metadata(
        metadata.to_dict()
    )


load_default_demo_document()


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #080d1c;
    }

    .block-container {
        max-width: 1100px;
        padding-top: 40px;
        padding-bottom: 60px;
    }

    .main-title {
        text-align: center;
        font-size: 34px;
        font-weight: 700;
        color: white;
        margin-bottom: 5px;
    }

    .main-subtitle {
        text-align: center;
        font-size: 15px;
        color: #9da9c0;
        margin-bottom: 30px;
    }

    .answer-box {
        background-color: #111827;
        border: 1px solid #263247;
        border-radius: 14px;
        padding: 24px;
        margin-top: 20px;
    }

    .verified {
        color: #63e6be;
        font-size: 17px;
        font-weight: 700;
    }

    .partial {
        color: #f6c85f;
        font-size: 17px;
        font-weight: 700;
    }

    .blocked {
        color: #ff7b7b;
        font-size: 17px;
        font-weight: 700;
    }

    .ambiguous {
        color: #f6c85f;
        font-size: 17px;
        font-weight: 700;
    }

    .evidence-box {
        background-color: #0d1424;
        border: 1px solid #263247;
        border-radius: 10px;
        padding: 15px;
        margin-top: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOGIN PAGE
# ============================================================

if st.session_state.user is None:

    st.markdown(
        '<div class="main-title">'
        '🛡️ LLM Hallucination Firewall'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">'
        'Secure Enterprise Knowledge Verification'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):

        st.subheader(
            "Secure Sign In"
        )

        st.write(
            "Sign in to access the enterprise knowledge system."
        )

        username = st.text_input(
            "Username",
            placeholder="Enter your username",
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
        )

        login_button = st.button(
            "Sign in securely",
            use_container_width=True,
        )

        if login_button:

            if (
                not username.strip()
                or not password
            ):

                st.warning(
                    "Please enter both username and password."
                )

            else:

                user = authenticate_user(
                    username.strip(),
                    password,
                )

                if user:

                    st.session_state.user = dict(
                        user
                    )

                    st.rerun()

                else:

                    st.error(
                        "Invalid username or password."
                    )

    st.markdown(
        '<div style="text-align:center;'
        'color:#63e6be;margin-top:25px;">'
        '● Authentication service ready'
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# MAIN APPLICATION
# ============================================================

else:

    user = st.session_state.user

    st.markdown(
        '<div class="main-title">'
        '🛡️ LLM Hallucination Firewall'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">'
        'Secure Enterprise Knowledge Verification'
        '</div>',
        unsafe_allow_html=True,
    )


    # ========================================================
    # USER INFORMATION
    # ========================================================

    col1, col2 = st.columns(
        [4, 1]
    )

    with col1:

        st.write(
            f"Welcome, **{user['full_name']}**"
        )

        st.caption(
            f"Role: {user['role'].title()}"
            + (
                f" • Department: {user['department']}"
                if user["department"]
                else ""
            )
        )

    with col2:

        if st.button(
            "Sign out",
            use_container_width=True,
        ):

            st.session_state.user = None

            st.rerun()


    st.divider()


    # ========================================================
    # DOCUMENT UPLOAD
    # ========================================================

    st.subheader(
        "📄 Enterprise Document Management"
    )

    st.caption(
        "Upload authorized college documents for enterprise search."
    )

    uploaded_file = st.file_uploader(
        "Upload PDF, DOCX or TXT",
        type=[
            "pdf",
            "docx",
            "txt",
        ],
    )


    if uploaded_file is not None:

        if user["role"].lower() in {
            "admin",
            "faculty",
        }:

            st.info(
                f"Selected: {uploaded_file.name}"
            )

            col1, col2, col3 = st.columns(
                3
            )

            with col1:

                department = st.selectbox(
                    "Department",
                    [
                        "Academic Affairs",
                        "CSE",
                        "ISE",
                        "ECE",
                        "EEE",
                        "ME",
                        "CE",
                        "Administration",
                        "College",
                        "General",
                    ],
                )

            with col2:

                document_type = st.selectbox(
                    "Document Type",
                    [
                        "Academic Policy",
                        "Attendance Policy",
                        "Examination Rule",
                        "Leave Policy",
                        "Department Guideline",
                        "Student Handbook",
                        "Faculty Guideline",
                        "Administrative Document",
                    ],
                )

            with col3:

                academic_year = st.number_input(
                    "Academic Year",
                    min_value=2020,
                    max_value=2100,
                    value=2026,
                    step=1,
                )


            col1, col2 = st.columns(
                2
            )

            with col1:

                version = st.text_input(
                    "Policy Version",
                    value="1.0",
                )

            with col2:

                effective_date = st.date_input(
                    "Effective Date"
                )


            allowed_roles = st.multiselect(
                "Who can access this document?",
                [
                    "student",
                    "faculty",
                    "staff",
                ],
                default=[
                    "student",
                    "faculty",
                    "staff",
                ],
            )


            if st.button(
                "⬆️ Add Document",
                type="primary",
                use_container_width=True,
            ):

                try:

                    target_path = (
                        DOCUMENT_DIRECTORY
                        / uploaded_file.name
                    )

                    target_path.write_bytes(
                        uploaded_file.getbuffer()
                    )


                    # Validate and extract text

                    document = load_document(
                        target_path
                    )


                    # Create metadata

                    metadata = create_metadata(
                        title=uploaded_file.name,
                        department=department,
                        document_type=document_type,
                        academic_year=int(
                            academic_year
                        ),
                        version=version,
                        effective_date=str(
                            effective_date
                        ),
                        allowed_roles=allowed_roles,
                        file_path=str(
                            target_path
                        ),
                    )


                    # Save metadata

                    add_document_metadata(
                        metadata.to_dict()
                    )


                    st.success(
                        f"Document '{uploaded_file.name}' "
                        "was added successfully."
                    )

                    st.rerun()


                except Exception as error:

                    st.error(
                        f"Document upload failed: {error}"
                    )

        else:

            st.warning(
                "Only Admin and Faculty users can upload documents."
            )


    # ========================================================
    # DOCUMENT LIST
    # ========================================================

    st.subheader(
        "📚 Registered Enterprise Documents"
    )

    registered_documents = (
        get_all_documents()
    )

    if not registered_documents:

        st.info(
            "No documents have been registered yet."
        )

    else:

        for document in registered_documents:

            title = document.get(
                "title",
                "Unknown document"
            )

            department = document.get(
                "department",
                "Unknown"
            )

            year = document.get(
                "academic_year",
                "N/A"
            )

            version = document.get(
                "version",
                "N/A"
            )

            st.write(
                f"📄 **{title}**  "
                f"• {department}  "
                f"• {year}  "
                f"• Version {version}"
            )


    st.divider()


    # ========================================================
    # KNOWLEDGE SEARCH
    # ========================================================

    st.subheader(
        "Ask the Enterprise Knowledge System"
    )

    query = st.text_area(
        "Ask a question",
        placeholder=(
            "Example: Can a 2nd year CSE student "
            "with 72% attendance write the 2026 "
            "semester exam?"
        ),
        height=100,
        label_visibility="collapsed",
    )


    verify_button = st.button(
        "🔎 Verify Answer",
        type="primary",
        use_container_width=True,
    )


    if verify_button:

        if not query.strip():

            st.warning(
                "Please enter a question."
            )

        else:

            with st.spinner(
                "Searching authorized evidence and verifying the answer..."
            ):

                documents = (
                    load_enterprise_documents()
                )

                pipeline = (
                    create_firewall_pipeline()
                )

                result = pipeline.process_query(
                    user,
                    query,
                    documents,
                )


            status = result.get(
                "status",
                "BLOCKED"
            )


            # =================================================
            # ANSWER
            # =================================================

            st.markdown(
                '<div class="answer-box">',
                unsafe_allow_html=True,
            )

            st.subheader(
                "Answer"
            )

            st.write(
                result.get(
                    "answer",
                    "No answer available."
                )
            )


            if status == "VERIFIED":

                st.markdown(
                    '<div class="verified">'
                    '🟢 VERIFIED'
                    '</div>',
                    unsafe_allow_html=True,
                )

            elif status == "PARTIALLY VERIFIED":

                st.markdown(
                    '<div class="partial">'
                    '🟡 PARTIALLY VERIFIED'
                    '</div>',
                    unsafe_allow_html=True,
                )

            elif status == "AMBIGUOUS":

                st.markdown(
                    '<div class="ambiguous">'
                    '🟠 AMBIGUOUS'
                    '</div>',
                    unsafe_allow_html=True,
                )

            elif status == "ACCESS DENIED":

                st.markdown(
                    '<div class="blocked">'
                    '🔴 ACCESS DENIED'
                    '</div>',
                    unsafe_allow_html=True,
                )

            else:

                st.markdown(
                    '<div class="blocked">'
                    '🔴 BLOCKED'
                    '</div>',
                    unsafe_allow_html=True,
                )


            st.write(
                f"**Verification:** "
                f"{result.get('reason', '')}"
            )


            st.markdown(
                '</div>',
                unsafe_allow_html=True,
            )


            # =================================================
            # EVIDENCE
            # =================================================

            evidence = result.get(
                "evidence",
                []
            )

            if evidence:

                st.subheader(
                    "Evidence"
                )

                for index, item in enumerate(
                    evidence,
                    start=1
                ):

                    title = item.get(
                        "title",
                        item.get(
                            "file_name",
                            "Unknown document"
                        ),
                    )

                    text = item.get(
                        "text",
                        ""
                    )

                    with st.expander(
                        f"Evidence {index} — {title}"
                    ):

                        st.write(
                            text
                        )

                        st.caption(
                            f"Version: "
                            f"{item.get('version', 'N/A')} "
                            f"• Academic Year: "
                            f"{item.get('academic_year', 'N/A')} "
                            f"• Effective Date: "
                            f"{item.get('effective_date', 'N/A')}"
                        )


            # =================================================
            # CLAIM VERIFICATION
            # =================================================

            claims = result.get(
                "claims",
                []
            )

            if claims:

                st.subheader(
                    "Claim Verification"
                )

                for claim in claims:

                    if claim.get(
                        "supported",
                        False
                    ):

                        st.success(
                            claim.get(
                                "claim",
                                ""
                            )
                        )

                        st.caption(
                            "Evidence match score: "
                            f"{claim.get('score', 0):.2f}"
                        )

                    else:

                        st.error(
                            claim.get(
                                "claim",
                                ""
                            )
                        )