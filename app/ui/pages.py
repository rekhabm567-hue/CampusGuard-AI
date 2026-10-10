# ============================================================
# UI PAGES
# LLM HALLUCINATION FIREWALL
# ============================================================

import streamlit as st


def render_login_page(authentication):
    """
    Login page.
    """

    st.title("LLM Hallucination Firewall")
    st.subheader("Enterprise Search Security Layer")

    st.write(
        "Sign in to access authorized college documents "
        "and verified answers."
    )

    username = st.text_input(
        "Username",
        key="login_username"
    )

    password = st.text_input(
        "Password",
        type="password",
        key="login_password"
    )

    if st.button(
        "Login",
        type="primary",
        use_container_width=True
    ):

        if not username or not password:

            st.error(
                "Please enter username and password."
            )
            return None

        user = authentication.authenticate(
            username,
            password
        )

        if user:

            st.session_state["authenticated_user"] = user

            st.success(
                "Login successful."
            )

            st.rerun()

        else:

            st.error(
                "Invalid username or password."
            )

    return None


# ============================================================
# HEADER
# ============================================================

def render_header(user):

    st.title(
        "LLM Hallucination Firewall"
    )

    st.caption(
        "Verified Enterprise Search for College Documents"
    )

    if user:

        role = user.get(
            "role",
            "user"
        )

        department = user.get(
            "department",
            "All"
        )

        st.info(
            f"Logged in as: {user.get('full_name', user.get('username', 'User'))} "
            f" | Role: {role.title()} "
            f" | Department: {department or 'All'}"
        )


# ============================================================
# DOCUMENT UPLOAD
# ============================================================

def render_document_upload(
    user,
    upload_callback
):

    role = str(
        user.get("role", "")
    ).lower()

    if role not in {
        "admin",
        "faculty"
    }:

        return

    st.subheader(
        "Document Management"
    )

    with st.expander(
        "Upload Enterprise Document"
    ):

        uploaded_file = st.file_uploader(
            "Choose a document",
            type=[
                "pdf",
                "docx",
                "txt"
            ],
            key="enterprise_document"
        )

        department = st.text_input(
            "Department",
            value=user.get(
                "department",
                "college"
            ) or "college"
        )

        document_type = st.selectbox(
            "Document Type",
            [
                "Academic Policy",
                "Examination Rule",
                "Attendance Policy",
                "Employee Rules",
                "Department Guideline",
                "Student Handbook",
                "Faculty Guideline",
                "Administrative Document",
                "Other"
            ]
        )

        academic_year = st.text_input(
            "Academic Year",
            value="2026"
        )

        version = st.text_input(
            "Document Version",
            value="1.0"
        )

        effective_date = st.date_input(
            "Effective Date"
        )

        allowed_roles = st.multiselect(
            "Users Allowed to Access",
            [
                "admin",
                "faculty",
                "student",
                "staff"
            ],
            default=[
                "admin",
                "faculty",
                "student",
                "staff"
            ]
        )

        if st.button(
            "Upload Document",
            type="primary",
            use_container_width=True
        ):

            if uploaded_file is None:

                st.warning(
                    "Please choose a document first."
                )
                return

            metadata = {
                "department": department,
                "document_type": document_type,
                "academic_year": academic_year,
                "version": version,
                "effective_date": str(
                    effective_date
                ),
                "allowed_roles": allowed_roles
            }

            result = upload_callback(
                uploaded_file,
                metadata
            )

            if result.get("success"):

                st.success(
                    result.get(
                        "message",
                        "Document uploaded successfully."
                    )
                )

                st.rerun()

            else:

                st.error(
                    result.get(
                        "message",
                        "Document upload failed."
                    )
                )


# ============================================================
# DOCUMENT LIST
# ============================================================

def render_document_list(
    documents
):

    st.subheader(
        "Authorized Enterprise Documents"
    )

    if not documents:

        st.info(
            "No enterprise documents are registered."
        )
        return

    for document in documents:

        title = document.get(
            "title",
            document.get(
                "file_name",
                "Untitled Document"
            )
        )

        department = document.get(
            "department",
            "General"
        )

        document_type = document.get(
            "document_type",
            "Document"
        )

        academic_year = document.get(
            "academic_year",
            "-"
        )

        version = document.get(
            "version",
            "-"
        )

        with st.container(
            border=True
        ):

            st.markdown(
                f"**{title}**"
            )

            st.caption(
                f"{document_type} | "
                f"Department: {department} | "
                f"Academic Year: {academic_year} | "
                f"Version: {version}"
            )


# ============================================================
# SEARCH SECTION
# ============================================================

def render_search_section(
    pipeline,
    user,
    documents
):

    st.subheader(
        "Ask the Enterprise Knowledge Base"
    )

    st.write(
        "Ask a question in natural language. "
        "The system retrieves only documents "
        "you are authorized to access."
    )

    query = st.text_area(
        "Your question",
        placeholder=(
            "Example: What are the employee rules?"
        ),
        height=100,
        key="enterprise_query"
    )

    if st.button(
        "Search and Verify",
        type="primary",
        use_container_width=True
    ):

        if not query.strip():

            st.warning(
                "Please enter a question."
            )
            return

        with st.spinner(
            "Searching authorized evidence and verifying the answer..."
        ):

            result = pipeline.process_query(
                user,
                query,
                documents
            )

        render_result(
            result
        )


# ============================================================
# RESULT
# ============================================================

def render_result(
    result
):

    status = result.get(
        "status",
        "BLOCKED"
    )

    answer = result.get(
        "answer",
        ""
    )

    evidence = result.get(
        "evidence",
        []
    )

    claims = result.get(
        "claims",
        []
    )

    reason = result.get(
        "reason",
        ""
    )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if status == "VERIFIED":

        st.success(
            "🟢 VERIFIED"
        )

        st.caption(
            "Verification: All generated claims are "
            "supported by retrieved evidence."
        )

    elif status == "PARTIALLY VERIFIED":

        st.warning(
            "🟡 PARTIALLY VERIFIED"
        )

        st.caption(
            "Some generated claims could not be "
            "fully supported by the retrieved evidence."
        )

    elif status == "AMBIGUOUS":

        st.warning(
            "🟠 AMBIGUOUS"
        )

        st.caption(
            "Conflicting or insufficient evidence "
            "prevents a definitive answer."
        )

    elif status == "ACCESS DENIED":

        st.error(
            "🔒 ACCESS DENIED"
        )

        st.caption(
            "The requested information is not "
            "available to your account."
        )

    else:

        st.error(
            "🔴 BLOCKED"
        )

        st.caption(
            "The answer was blocked because "
            "sufficient supporting evidence was not found."
        )

    # --------------------------------------------------------
    # ANSWER
    # --------------------------------------------------------

    st.subheader(
        "Answer"
    )

    st.markdown(
        answer
    )

    # --------------------------------------------------------
    # EVIDENCE
    # --------------------------------------------------------

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
                    "Enterprise Document"
                )
            )

            text = item.get(
                "text",
                ""
            )

            st.markdown(
                f"**Evidence {index} — {title}**"
            )

            # Do not display retrieval scores.
            # The scores remain internal to the
            # retrieval and firewall pipeline.

            if text:

                with st.expander(
                    "View supporting document text"
                ):

                    st.write(
                        text
                    )

    # --------------------------------------------------------
    # CLAIM VERIFICATION
    # --------------------------------------------------------

    if claims:

        st.subheader(
            "Claim Verification"
        )

        for index, claim in enumerate(
            claims,
            start=1
        ):

            # The claim extractor may return either
            # a dictionary or a plain string.
            if isinstance(
                claim,
                dict
            ):

                claim_text = claim.get(
                    "claim",
                    claim.get(
                        "text",
                        ""
                    )
                )

                verified = claim.get(
                    "verified",
                    True
                )

                # IMPORTANT:
                # Do not display the internal evidence
                # similarity score to the user.

            else:

                claim_text = str(
                    claim
                )

                verified = True

            if not claim_text:
                continue

            if verified:

                st.markdown(
                    f"**{index}.** "
                    f"🟢 {claim_text}"
                )

            else:

                st.markdown(
                    f"**{index}.** "
                    f"🔴 {claim_text}"
                )

    # --------------------------------------------------------
    # FIREWALL REASON
    # --------------------------------------------------------

    if reason:

        with st.expander(
            "Firewall Decision Details"
        ):

            st.write(
                reason
            )


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar(
    user
):

    with st.sidebar:

        st.header(
            "LLM Hallucination Firewall"
        )

        st.caption(
            "Enterprise Search Security"
        )

        st.divider()

        if user:

            st.write(
                f"**User:** "
                f"{user.get('full_name', user.get('username', 'User'))}"
            )

            st.write(
                f"**Role:** "
                f"{str(user.get('role', 'user')).title()}"
            )

            department = user.get(
                "department"
            )

            st.write(
                f"**Department:** "
                f"{department or 'All'}"
            )

            st.divider()

            if st.button(
                "Logout",
                use_container_width=True
            ):

                st.session_state.pop(
                    "authenticated_user",
                    None
                )

                st.rerun()


# ============================================================
# MAIN APPLICATION PAGE
# ============================================================

def render_main_page(
    user,
    pipeline,
    documents,
    upload_callback=None
):

    render_sidebar(
        user
    )

    render_header(
        user
    )

    if upload_callback:

        render_document_upload(
            user,
            upload_callback
        )

    render_search_section(
        pipeline,
        user,
        documents
    )

    st.divider()

    render_document_list(
        documents
    )