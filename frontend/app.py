import os
import sys
from pathlib import Path

# Ensure project root is in sys.path regardless of execution directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List

try:
    import frontend.api as api
except ModuleNotFoundError:
    import api as api

# ── Page Configuration ─────────────────────────────────────
st.set_page_config(
    page_title="SmartApply — AI Job Tracker & Optimizer",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for Rich Modern Aesthetics ─────────────────
st.markdown(
    """
<style>
    /* Global Styles & Variables */
    :root {
        --primary-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        --card-bg: rgba(255, 255, 255, 0.05);
        --card-border: rgba(255, 255, 255, 0.1);
        --card-hover: rgba(255, 255, 255, 0.08);
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    /* App Header Gradient */
    .app-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(120deg, #6366f1, #8b5cf6, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .app-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }

    /* KPI Metric Cards */
    .kpi-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 14px 18px;
        text-align: left;
        backdrop-filter: blur(8px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .kpi-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
    }

    /* Kanban Column Headers */
    .kanban-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 14px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 12px;
    }
    .col-saved { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border-left: 4px solid #94a3b8; }
    .col-applied { background: rgba(59, 130, 246, 0.15); color: #93c5fd; border-left: 4px solid #3b82f6; }
    .col-interview { background: rgba(168, 85, 247, 0.15); color: #d8b4fe; border-left: 4px solid #a855f7; }
    .col-offer { background: rgba(34, 197, 94, 0.15); color: #86efac; border-left: 4px solid #22c55e; }
    .col-rejected { background: rgba(239, 68, 68, 0.15); color: #fca5a5; border-left: 4px solid #ef4444; }

    /* Job Card Styling */
    .job-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    .job-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 8px 20px -4px rgba(0, 0, 0, 0.25);
    }
    .job-company {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .job-role {
        font-size: 0.9rem;
        color: #cbd5e1;
        margin-bottom: 8px;
    }
    .job-date {
        font-size: 0.75rem;
        color: #64748b;
    }

    /* Score Badge */
    .score-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .score-high { background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); }
    .score-med { background: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.4); }
    .score-low { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .score-none { background: rgba(148, 163, 184, 0.1); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.2); }

    /* Skill Tags */
    .skill-tag-match {
        display: inline-block;
        background: rgba(34, 197, 94, 0.15);
        color: #86efac;
        border: 1px solid rgba(34, 197, 94, 0.3);
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        margin: 2px;
    }
    .skill-tag-missing {
        display: inline-block;
        background: rgba(239, 68, 68, 0.15);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        margin: 2px;
    }

    /* Email Box Highlights */
    .email-preview-box {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 8px;
        padding: 12px;
        margin-top: 10px;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ── Session State Management ──────────────────────────────
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = {}
if "cover_letters" not in st.session_state:
    st.session_state.cover_letters = {}
if "sample_email_body" not in st.session_state:
    st.session_state.sample_email_body = ""
if "sample_email_subject" not in st.session_state:
    st.session_state.sample_email_subject = ""
if "sample_email_sender" not in st.session_state:
    st.session_state.sample_email_sender = ""

# ── Sample Data Helpers ───────────────────────────────────
SAMPLE_RESUME = """Jane Doe
Senior Full-Stack Software Engineer
Email: jane.doe@example.com | GitHub: github.com/janedoe | LinkedIn: linkedin.com/in/janedoe

SUMMARY:
Results-driven Senior Full-Stack Engineer with 6+ years of experience architecting high-scale web applications, microservices, and AI integrations. Proficient in Python, FastAPI, React, PostgreSQL, Docker, and AWS.

EXPERIENCE:
Senior Software Engineer | TechScale Inc. (2022 - Present)
- Architected and deployed microservices backend in Python (FastAPI) and PostgreSQL, handling 15k requests/sec with 99.99% uptime.
- Integrated Anthropic and OpenAI LLM endpoints with prompt caching, reducing latency by 40%.
- Led a team of 5 engineers, establishing CI/CD pipelines using GitHub Actions and Kubernetes.

Full-Stack Developer | CloudNova Solutions (2019 - 2022)
- Built interactive customer analytics dashboards using React, TypeScript, and Streamlit.
- Designed database schemas and optimized SQL queries on PostgreSQL, reducing query execution time by 60%.
- Implemented OAuth2 authentication and role-based access control (RBAC).

SKILLS:
- Languages: Python, JavaScript, TypeScript, SQL, HTML/CSS
- Frameworks: FastAPI, Flask, React, Next.js, Streamlit, Pydantic, asyncpg
- Databases & Cloud: PostgreSQL, Redis, Docker, AWS (EC2, S3, RDS), Git, Linux

EDUCATION:
B.S. in Computer Science | University of California, Berkeley (2015 - 2019)
"""

SAMPLE_CONFIRMATION_EMAIL = {
    "subject": "Thank you for applying to Stripe — Senior Backend Engineer",
    "sender": "recruiting@stripe.com",
    "body": """Hi Jane,

Thank you for your interest in Stripe! We have received your application for the Senior Backend Engineer role.

Our engineering recruitment team is currently reviewing your profile and qualifications. We typically follow up within 3-5 business days regarding next steps in our interview process.

You can track your application status at anytime through our candidate portal.

Best regards,
The Stripe Recruiting Team""",
}

SAMPLE_INTERVIEW_EMAIL = {
    "subject": "Invitation to Interview: Google - Software Engineer III",
    "sender": "no-reply-careers@google.com",
    "body": """Hello Jane,

We were very impressed by your background and experience. We would love to invite you to a 45-minute technical screening interview for the Software Engineer III role at Google.

Please reply to this email or follow the calendar link below to select a time that works best for your schedule:
https://careers.google.com/interview/schedule/abc123xyz

We look forward to speaking with you!

Warmly,
Google Talent Acquisition""",
}

SAMPLE_REJECTION_EMAIL = {
    "subject": "Update on your application with Netflix",
    "sender": "talent@netflix.com",
    "body": """Dear Jane,

Thank you for taking the time to speak with our engineering team for the Senior Distributed Systems Engineer position.

While we were impressed with your technical background, we have decided to move forward with candidates whose experience more closely matches our immediate project needs.

We appreciate your interest in Netflix and wish you the best in your career search.

Sincerely,
Netflix Talent Team""",
}

# ── Sidebar Navigation & Inputs ───────────────────────────
with st.sidebar:
    st.markdown("### 💼 **SmartApply Hub**")

    # Backend Connection Status
    is_healthy = api.check_health()
    if is_healthy:
        st.markdown("🟢 **Backend Connected** (`http://localhost:8000`)")
    else:
        st.markdown("🔴 **Backend Offline**")
        st.caption("Run `uvicorn backend.main:app --reload` in your terminal to start.")

    st.markdown("---")

    # 1. Resume Manager Section
    st.subheader("📄 1. Master Resume")
    col_res1, col_res2 = st.columns([1, 1])
    with col_res1:
        if st.button("Load Sample Resume", use_container_width=True):
            st.session_state.resume_text = SAMPLE_RESUME
            st.rerun()
    with col_res2:
        if st.button("Clear Resume", use_container_width=True):
            st.session_state.resume_text = ""
            st.rerun()

    resume_input = st.text_area(
        "Paste your plain-text resume here:",
        value=st.session_state.resume_text,
        height=180,
        placeholder="Paste plain text resume here...",
        help="This resume will be compared against job descriptions to calculate match scores and generate tailored cover letters.",
    )
    if resume_input != st.session_state.resume_text:
        st.session_state.resume_text = resume_input

    char_count = len(st.session_state.resume_text)
    word_count = len(st.session_state.resume_text.split()) if char_count > 0 else 0
    st.caption(f"📊 {word_count} words | {char_count} characters")

    st.markdown("---")

    # 2. Add New Job Application Form
    st.subheader("➕ 2. Add New Job")
    with st.form("add_job_form", clear_on_submit=True):
        new_company = st.text_input("Company Name*", placeholder="e.g. Stripe")
        new_role = st.text_input("Role Title*", placeholder="e.g. Senior Backend Engineer")
        new_url = st.text_input("Job Posting URL", placeholder="https://jobs.stripe.com/...")
        new_desc = st.text_area(
            "Job Description (JD)",
            height=120,
            placeholder="Paste the key responsibilities, requirements, and qualifications...",
        )
        new_notes = st.text_input("Notes / Referral", placeholder="e.g. Referred by Alex; Applied via LinkedIn")

        submit_job = st.form_submit_button("Track Application", use_container_width=True)

        if submit_job:
            if not new_company.strip() or not new_role.strip():
                st.error("Please provide both Company Name and Role Title.")
            else:
                try:
                    res = api.create_job(
                        company=new_company,
                        role=new_role,
                        job_url=new_url,
                        job_description=new_desc,
                        notes=new_notes,
                    )
                    st.success(f"Added {new_role} at {new_company}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating job: {e}")


# ── Main Content Area ─────────────────────────────────────
# Header
col_header, col_status = st.columns([3, 1])
with col_header:
    st.markdown('<div class="app-title">SmartApply AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">Track your pipeline, auto-sync email confirmations, analyze resume compatibility, and generate cover letters.</div>',
        unsafe_allow_html=True,
    )

# Fetch Jobs from Backend
jobs: List[Dict[str, Any]] = []
fetch_error = None
try:
    if is_healthy:
        jobs = api.get_jobs()
except Exception as e:
    fetch_error = str(e)

if not is_healthy:
    st.warning(
        "⚠️ **FastAPI Backend Server is not running.**\n\n"
        "To start the backend, open a terminal in the project directory and run:\n"
        "```bash\n"
        "source venv/bin/activate\n"
        "uvicorn backend.main:app --reload\n"
        "```"
    )
elif fetch_error:
    st.error(f"Error fetching applications: {fetch_error}")

# ── Summary Metrics KPIs ──────────────────────────────────
total_jobs = len(jobs)
applied_count = sum(1 for j in jobs if j.get("status") in ["applied", "interview", "offer"])
interview_count = sum(1 for j in jobs if j.get("status") == "interview")
offer_count = sum(1 for j in jobs if j.get("status") == "offer")
scores = [j["match_score"] for j in jobs if j.get("match_score") is not None]
avg_score = round(sum(scores) / len(scores)) if scores else None

kpi_cols = st.columns(5)
with kpi_cols[0]:
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">Total Tracked</div><div class="kpi-value">{total_jobs}</div></div>',
        unsafe_allow_html=True,
    )
with kpi_cols[1]:
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">In Pipeline</div><div class="kpi-value">{applied_count}</div></div>',
        unsafe_allow_html=True,
    )
with kpi_cols[2]:
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">Interviews</div><div class="kpi-value">{interview_count}</div></div>',
        unsafe_allow_html=True,
    )
with kpi_cols[3]:
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">Offers</div><div class="kpi-value">{offer_count}</div></div>',
        unsafe_allow_html=True,
    )
with kpi_cols[4]:
    score_display = f"{avg_score}%" if avg_score is not None else "N/A"
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">Avg Match Score</div><div class="kpi-value">{score_display}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Helper: Format Score Badge ────────────────────────────
def render_score_badge(score):
    if score is None:
        return '<span class="score-badge score-none">No Score</span>'
    if score >= 80:
        return f'<span class="score-badge score-high">{score}% Match</span>'
    elif score >= 60:
        return f'<span class="score-badge score-med">{score}% Match</span>'
    else:
        return f'<span class="score-badge score-low">{score}% Match</span>'


# ── View Tabs: Kanban Board vs Table View vs Analytics vs Email Automation ────
tab_kanban, tab_table, tab_analytics, tab_email = st.tabs([
    "📋 Kanban Board",
    "📄 Table View",
    "📊 Analytics",
    "📧 Email Automation",
])

# ──────────────────────────────────────────────────────────
# TAB 1: KANBAN BOARD
# ──────────────────────────────────────────────────────────
with tab_kanban:
    filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])
    with filter_col1:
        search_term = st.text_input(
            "🔍 Search applications",
            placeholder="Filter by company, role, notes...",
            label_visibility="collapsed",
            key="kanban_search",
        )
    with filter_col2:
        stage_filter = st.selectbox(
            "Filter Stage",
            ["All Stages", "saved", "applied", "interview", "offer", "rejected"],
            label_visibility="collapsed",
            key="kanban_stage_filter",
        )
    with filter_col3:
        if st.button("🔄 Refresh Data", use_container_width=True, key="kanban_refresh"):
            st.rerun()

    # Apply local search filtering
    filtered_jobs = jobs
    if search_term.strip():
        q = search_term.lower()
        filtered_jobs = [
            j
            for j in filtered_jobs
            if q in (j.get("company") or "").lower()
            or q in (j.get("role") or "").lower()
            or q in (j.get("notes") or "").lower()
        ]
    if stage_filter != "All Stages":
        filtered_jobs = [j for j in filtered_jobs if j.get("status") == stage_filter]

    stages = [
        ("saved", "📌 Saved", "col-saved"),
        ("applied", "✉️ Applied", "col-applied"),
        ("interview", "💬 Interview", "col-interview"),
        ("offer", "🎉 Offer", "col-offer"),
        ("rejected", "❌ Rejected", "col-rejected"),
    ]

    kanban_cols = st.columns(5)

    for idx, (stage_key, stage_label, col_class) in enumerate(stages):
        with kanban_cols[idx]:
            stage_jobs = [j for j in filtered_jobs if j.get("status") == stage_key]
            st.markdown(
                f'<div class="kanban-header {col_class}"><span>{stage_label}</span><span>({len(stage_jobs)})</span></div>',
                unsafe_allow_html=True,
            )

            if not stage_jobs:
                st.caption("No applications.")

            for job in stage_jobs:
                job_id = str(job["id"])
                company = job.get("company", "Unknown")
                role = job.get("role", "Unknown")
                score = job.get("match_score")
                url = job.get("job_url")
                notes = job.get("notes")
                has_jd = bool(job.get("job_description"))

                # Format date
                date_str = ""
                if job.get("applied_date"):
                    try:
                        raw_date = job["applied_date"]
                        if isinstance(raw_date, str):
                            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                        else:
                            dt = raw_date
                        date_str = dt.strftime("%b %d, %Y")
                    except Exception:
                        date_str = str(job.get("applied_date"))[:10]

                with st.container():
                    # Card Header
                    score_badge_html = render_score_badge(score)
                    st.markdown(
                        f"""
                        <div class="job-card">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                <div class="job-company">{company}</div>
                                {score_badge_html}
                            </div>
                            <div class="job-role">{role}</div>
                            <div class="job-date">📅 {date_str}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Quick links & notes if present
                    if url:
                        st.markdown(f"[🔗 View Job Posting]({url})")
                    if notes:
                        st.caption(f"📝 {notes}")

                    # Card Controls in Expander
                    with st.expander("⚡ Actions & AI Tools", expanded=False):
                        # Stage Mover
                        current_status = job.get("status", "saved")
                        stage_options = ["saved", "applied", "interview", "offer", "rejected"]
                        new_stage = st.selectbox(
                            "Move Stage:",
                            options=stage_options,
                            index=stage_options.index(current_status),
                            key=f"stage_select_{job_id}",
                        )
                        if new_stage != current_status:
                            try:
                                api.update_job_status(job_id, new_stage)
                                st.success(f"Moved to {new_stage}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

                        # AI Match Analysis Action
                        if st.button(
                            "🧠 Run AI Fit Analysis",
                            key=f"btn_analyze_{job_id}",
                            use_container_width=True,
                            disabled=not has_jd,
                            help="Requires a job description and master resume text." if not has_jd else None,
                        ):
                            if not st.session_state.resume_text.strip():
                                st.error("Please paste your resume in the sidebar first!")
                            elif not has_jd:
                                st.error("This job record has no job description saved.")
                            else:
                                with st.spinner(f"Analyzing fit for {role} at {company}..."):
                                    try:
                                        result = api.analyze_resume(job_id, st.session_state.resume_text)
                                        st.session_state.analysis_results[job_id] = result
                                        st.success("Analysis complete!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Analysis failed: {e}")

                        # Cover Letter Generator Action
                        if st.button(
                            "✍️ Generate Cover Letter",
                            key=f"btn_cover_{job_id}",
                            use_container_width=True,
                            disabled=not has_jd,
                        ):
                            if not st.session_state.resume_text.strip():
                                st.error("Please paste your resume in the sidebar first!")
                            else:
                                with st.spinner(f"Drafting tailored cover letter for {company}..."):
                                    try:
                                        letter = api.generate_cover_letter(job_id, st.session_state.resume_text)
                                        st.session_state.cover_letters[job_id] = letter
                                        st.success("Cover letter generated!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Cover letter generation failed: {e}")

                        # Delete Job
                        if st.button("🗑️ Delete Application", key=f"btn_del_{job_id}", use_container_width=True):
                            try:
                                api.delete_job(job_id)
                                st.success(f"Deleted application for {company}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")

                    # Display Stored Analysis if available
                    analysis = st.session_state.analysis_results.get(job_id)
                    if analysis:
                        with st.expander(f"📊 AI Analysis ({company})", expanded=True):
                            match_score_val = analysis.get("match_score", 0)
                            st.progress(match_score_val / 100, text=f"Fit Score: {match_score_val}%")

                            st.markdown(f"**Summary**: {analysis.get('summary', 'N/A')}")

                            # Matched & Missing Skills
                            matched = analysis.get("matched_skills", [])
                            missing = analysis.get("missing_skills", [])

                            if matched:
                                st.markdown("**✅ Matching Skills:**")
                                tags_html = "".join([f'<span class="skill-tag-match">{s}</span>' for s in matched])
                                st.markdown(tags_html, unsafe_allow_html=True)

                            if missing:
                                st.markdown("**⚠️ Missing / Recommended Skills:**")
                                tags_html = "".join([f'<span class="skill-tag-missing">{s}</span>' for s in missing])
                                st.markdown(tags_html, unsafe_allow_html=True)

                            feedback = analysis.get("section_feedback", {})
                            if feedback:
                                st.markdown("**💡 Section Feedback:**")
                                for sec, fb in feedback.items():
                                    st.markdown(f"- **{sec.capitalize()}**: {fb}")

                    # Display Stored Cover Letter if available
                    saved_letter = job.get("cover_letter") or st.session_state.cover_letters.get(job_id)
                    if saved_letter:
                        with st.expander(f"✉️ Cover Letter ({company})", expanded=False):
                            st.text_area(
                                "Tailored Letter",
                                value=saved_letter,
                                height=200,
                                key=f"txt_cl_{job_id}",
                            )
                            st.download_button(
                                "📥 Download Letter (.txt)",
                                data=saved_letter,
                                file_name=f"Cover_Letter_{company}_{role}.txt".replace(" ", "_"),
                                mime="text/plain",
                                key=f"dl_cl_{job_id}",
                                use_container_width=True,
                            )

                    st.markdown("<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.05);'>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────
# TAB 2: TABLE VIEW
# ──────────────────────────────────────────────────────────
with tab_table:
    if not jobs:
        st.info("No applications in your tracker yet.")
    else:
        table_data = []
        for j in jobs:
            table_data.append(
                {
                    "Company": j.get("company"),
                    "Role": j.get("role"),
                    "Status": j.get("status", "").upper(),
                    "Match Score": f"{j.get('match_score')}%" if j.get("match_score") is not None else "N/A",
                    "Applied Date": str(j.get("applied_date"))[:10],
                    "URL": j.get("job_url") or "",
                    "Notes": j.get("notes") or "",
                }
            )
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # CSV Export
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Export to CSV",
            data=csv,
            file_name=f"SmartApply_Applications_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )


# ──────────────────────────────────────────────────────────
# TAB 3: ANALYTICS VIEW
# ──────────────────────────────────────────────────────────
with tab_analytics:
    if not jobs:
        st.info("Add application records to see analytics breakdown.")
    else:
        st.subheader("📈 Application Pipeline Breakdown")

        # Stage distribution chart
        stage_counts = {
            "Saved": sum(1 for j in jobs if j.get("status") == "saved"),
            "Applied": sum(1 for j in jobs if j.get("status") == "applied"),
            "Interview": sum(1 for j in jobs if j.get("status") == "interview"),
            "Offer": sum(1 for j in jobs if j.get("status") == "offer"),
            "Rejected": sum(1 for j in jobs if j.get("status") == "rejected"),
        }
        df_stages = pd.DataFrame(
            {"Stage": list(stage_counts.keys()), "Count": list(stage_counts.values())}
        )
        st.bar_chart(df_stages.set_index("Stage"))

        # Score distribution
        scored_jobs = [j for j in jobs if j.get("match_score") is not None]
        if scored_jobs:
            st.subheader("🎯 Resume Match Scores by Application")
            df_scores = pd.DataFrame(
                [
                    {
                        "Application": f"{j.get('company')} - {j.get('role')}",
                        "Match Score": j.get("match_score"),
                    }
                    for j in scored_jobs
                ]
            )
            st.bar_chart(df_scores.set_index("Application"))


# ──────────────────────────────────────────────────────────
# TAB 4: EMAIL AUTOMATION HUB
# ──────────────────────────────────────────────────────────
with tab_email:
    st.subheader("📧 Automated Email Confirmation & Status Sync")
    st.markdown(
        "SmartApply connects to your inbox to auto-detect job application confirmations, "
        "interview invitations, and status updates, keeping your pipeline updated in real-time."
    )

    col_sync_ctrl, col_guide = st.columns([1.5, 1])

    with col_sync_ctrl:
        st.markdown("#### ⚡ 1. Sync Inbox")
        sync_limit = st.slider("Max unread emails to scan:", min_value=5, max_value=30, value=10)
        if st.button("🚀 Sync Inbox Emails Now", use_container_width=True, type="primary"):
            with st.spinner("Connecting to mail server & parsing new confirmation emails with Claude..."):
                try:
                    sync_res = api.sync_inbox_emails(limit=sync_limit)
                    processed_count = sync_res.get("processed_count", 0)
                    actions = sync_res.get("actions", [])
                    st.success(f"✅ Sync complete! Scanned {processed_count} emails.")

                    if actions:
                        st.markdown("**Sync Results:**")
                        for a in actions:
                            if a.get("status") == "success":
                                st.info(f"✨ **{a.get('action', '').upper()}**: {a.get('company')} ({a.get('role')}) -> Stage: `{a.get('stage')}` — {a.get('summary')}")
                            elif a.get("status") == "skipped":
                                st.caption(f"⏭️ Skipped (Already processed)")
                    else:
                        st.caption("No new job confirmation emails found in scanned batch.")
                except Exception as e:
                    st.error(f"Inbox Sync Error: {e}")
                    st.info("💡 Make sure your email credentials (`EMAIL_ADDRESS` & `EMAIL_APP_PASSWORD`) are set in your `.env` file, or test with the sandbox below!")

    with col_guide:
        with st.expander("⚙️ Email IMAP Setup Guide", expanded=False):
            st.markdown(
                """
                **How to connect your Gmail/Outlook:**
                1. **Gmail**:
                   - Go to **Google Account Settings** > **Security** > **2-Step Verification**.
                   - At the bottom, click **App Passwords**.
                   - Create an App Password named `SmartApply`.
                2. Open `.env` and add:
                   ```ini
                   EMAIL_IMAP_SERVER=imap.gmail.com
                   EMAIL_IMAP_PORT=993
                   EMAIL_ADDRESS=your.email@gmail.com
                   EMAIL_APP_PASSWORD=your-16-char-app-password
                   ```
                3. Restart or click Sync!
                """
            )

    st.markdown("---")

    # Instant Email Test Sandbox
    st.markdown("#### 🧪 2. Instant Email Parser Sandbox")
    st.caption("Test how Claude parses confirmation emails and automatically creates or moves jobs in your pipeline.")

    # Sample Buttons
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        if st.button("📝 Load Application Confirmation"):
            st.session_state.sample_email_subject = SAMPLE_CONFIRMATION_EMAIL["subject"]
            st.session_state.sample_email_sender = SAMPLE_CONFIRMATION_EMAIL["sender"]
            st.session_state.sample_email_body = SAMPLE_CONFIRMATION_EMAIL["body"]
            st.rerun()
    with col_s2:
        if st.button("💬 Load Interview Invite"):
            st.session_state.sample_email_subject = SAMPLE_INTERVIEW_EMAIL["subject"]
            st.session_state.sample_email_sender = SAMPLE_INTERVIEW_EMAIL["sender"]
            st.session_state.sample_email_body = SAMPLE_INTERVIEW_EMAIL["body"]
            st.rerun()
    with col_s3:
        if st.button("❌ Load Rejection Notice"):
            st.session_state.sample_email_subject = SAMPLE_REJECTION_EMAIL["subject"]
            st.session_state.sample_email_sender = SAMPLE_REJECTION_EMAIL["sender"]
            st.session_state.sample_email_body = SAMPLE_REJECTION_EMAIL["body"]
            st.rerun()
    with col_s4:
        if st.button("🧹 Clear Box"):
            st.session_state.sample_email_subject = ""
            st.session_state.sample_email_sender = ""
            st.session_state.sample_email_body = ""
            st.rerun()

    col_in1, col_in2 = st.columns(2)
    with col_in1:
        em_subject = st.text_input("Email Subject:", value=st.session_state.sample_email_subject, placeholder="e.g. Thank you for applying to Stripe")
    with col_in2:
        em_sender = st.text_input("Sender / From:", value=st.session_state.sample_email_sender, placeholder="e.g. jobs@stripe.com")

    em_body = st.text_area(
        "Email Body Text:",
        value=st.session_state.sample_email_body,
        height=150,
        placeholder="Paste full confirmation email text here...",
    )

    if st.button("🧠 Parse Email & Update SmartApply Tracker", use_container_width=True):
        if not em_body.strip():
            st.error("Please paste email body text to test.")
        else:
            with st.spinner("Extracting company, role, and application status with Claude..."):
                try:
                    parse_res = api.parse_raw_email(
                        body=em_body,
                        subject=em_subject or "Job Application Update",
                        sender=em_sender or "careers@company.com",
                    )
                    st.success("Email successfully analyzed and pipeline updated!")

                    st.markdown(
                        f"""
                        <div class="email-preview-box">
                            <div style="font-size: 1.1rem; font-weight: 700; color: #a855f7;">🎯 Extraction Result</div>
                            <ul style="margin-top: 8px; color: #f1f5f9;">
                                <li><b>Action Taken:</b> <span style="text-transform: uppercase; color: #4ade80;">{parse_res.get('action', 'N/A')}</span></li>
                                <li><b>Company:</b> {parse_res.get('company', 'Unknown')}</li>
                                <li><b>Role:</b> {parse_res.get('role', 'Unknown')}</li>
                                <li><b>Detected Stage:</b> <code>{parse_res.get('stage', 'N/A')}</code></li>
                                <li><b>Summary:</b> {parse_res.get('summary', 'N/A')}</li>
                            </ul>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    st.error(f"Parsing failed: {e}")

    st.markdown("---")

    # 3. Email Sync Activity Log Table
    st.markdown("#### 📜 3. Recent Email Sync History")
    email_logs = []
    try:
        if is_healthy:
            email_logs = api.get_email_logs(limit=25)
    except Exception:
        pass

    if not email_logs:
        st.caption("No email sync events recorded yet.")
    else:
        log_records = []
        for l in email_logs:
            log_records.append(
                {
                    "Processed At": str(l.get("processed_at"))[:19].replace("T", " "),
                    "Company": l.get("company") or "N/A",
                    "Role": l.get("role") or "N/A",
                    "Stage": (l.get("detected_status") or "N/A").upper(),
                    "Action": (l.get("action_taken") or "N/A").upper(),
                    "Subject": l.get("subject") or "",
                    "Summary": l.get("summary") or "",
                }
            )
        df_logs = pd.DataFrame(log_records)
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
