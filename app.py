import os
import re
import json
import sqlite3
import hashlib
import html as html_mod
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
import anthropic

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FREE_ANALYSIS_LIMIT = 3
STRIPE_CHECKOUT_URL = "https://buy.stripe.com/PLACEHOLDER"  # Replace with real Stripe link
DB_PATH = Path(__file__).parent / "usage.db"
TOKENS_PATH = Path(__file__).parent / "valid_tokens.txt"

# ---------------------------------------------------------------------------
# Page config — title, favicon, meta description
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Immigration Case Manager",
    page_icon="🍁",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": (
            "AI Immigration Case Manager — Intelligent case preparation for "
            "Canadian immigration pathways. Built with Streamlit and Claude."
        ),
    },
)

# ---------------------------------------------------------------------------
# Custom CSS — including mobile responsive styles
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Header bar */
    .main-header {
        background: linear-gradient(135deg, #1B4D3E 0%, #2E7D5B 100%);
        padding: 1.5rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: #C8E6C9;
        margin: 0.25rem 0 0 0;
        font-size: 0.95rem;
    }

    /* Step indicators */
    .step-container {
        display: flex;
        justify-content: center;
        gap: 0.5rem;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
    }
    .step {
        padding: 0.5rem 1.5rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .step-active {
        background-color: #1B4D3E;
        color: white;
    }
    .step-inactive {
        background-color: #E8E8E8;
        color: #888;
    }
    .step-done {
        background-color: #C8E6C9;
        color: #1B4D3E;
    }

    /* Section cards */
    .section-card {
        background: white;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .section-card h3 { margin-top: 0; }

    /* Risk colours */
    .risk-green {
        border-left: 4px solid #4CAF50;
        padding-left: 1rem;
        margin-bottom: 0.75rem;
    }
    .risk-yellow {
        border-left: 4px solid #FFC107;
        padding-left: 1rem;
        margin-bottom: 0.75rem;
    }
    .risk-red {
        border-left: 4px solid #F44336;
        padding-left: 1rem;
        margin-bottom: 0.75rem;
    }

    /* Disclaimer */
    .disclaimer {
        background: #FFF3E0;
        border: 1px solid #FFE0B2;
        border-radius: 8px;
        padding: 1rem;
        font-size: 0.85rem;
        color: #E65100;
        margin-top: 1.5rem;
    }

    /* Upgrade banner */
    .upgrade-box {
        background: linear-gradient(135deg, #1B4D3E 0%, #2E7D5B 100%);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        color: white;
        margin: 2rem 0;
    }
    .upgrade-box h2 { color: white !important; margin-bottom: 0.5rem; }
    .upgrade-box p { color: #C8E6C9; margin-bottom: 1.5rem; }

    /* Usage badge */
    .usage-badge {
        background: #F0F4F2;
        border: 1px solid #DDD;
        border-radius: 8px;
        padding: 0.4rem 0.8rem;
        font-size: 0.8rem;
        color: #555;
        display: inline-block;
        margin-bottom: 1rem;
    }

    /* Reduce top padding */
    .block-container { padding-top: 1rem; }

    /* Mobile responsive */
    @media (max-width: 768px) {
        .main-header { padding: 1rem; }
        .main-header h1 { font-size: 1.3rem; }
        .step { padding: 0.35rem 0.8rem; font-size: 0.75rem; }
        .section-card { padding: 0.75rem; }
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SQLite usage tracking
# ---------------------------------------------------------------------------
def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS usage ("
        "  ip_hash TEXT PRIMARY KEY,"
        "  count INTEGER DEFAULT 0"
        ")"
    )
    conn.commit()
    return conn


def _ip_hash() -> str:
    """Produce a SHA-256 hash of the user's IP for privacy-safe tracking."""
    # st.context.headers is available in Streamlit >= 1.31
    headers = getattr(st.context, "headers", {}) if hasattr(st, "context") else {}
    raw_ip = (
        headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or headers.get("X-Real-Ip", "")
        or "unknown"
    )
    return hashlib.sha256(raw_ip.encode()).hexdigest()


def get_usage_count() -> int:
    conn = _get_db()
    row = conn.execute(
        "SELECT count FROM usage WHERE ip_hash = ?", (_ip_hash(),)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def increment_usage() -> int:
    conn = _get_db()
    ip = _ip_hash()
    conn.execute(
        "INSERT INTO usage (ip_hash, count) VALUES (?, 1) "
        "ON CONFLICT(ip_hash) DO UPDATE SET count = count + 1",
        (ip,),
    )
    conn.commit()
    row = conn.execute("SELECT count FROM usage WHERE ip_hash = ?", (ip,)).fetchone()
    conn.close()
    return row[0] if row else 1


# ---------------------------------------------------------------------------
# Access token validation (paid-user bypass)
# ---------------------------------------------------------------------------
def _load_valid_tokens() -> set[str]:
    if TOKENS_PATH.exists():
        return {
            line.strip()
            for line in TOKENS_PATH.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
    return set()


def is_valid_token(token: str) -> bool:
    return token.strip() in _load_valid_tokens()


# ---------------------------------------------------------------------------
# Input sanitization
# ---------------------------------------------------------------------------
_SAFE_TEXT = re.compile(r"[^\w\s\-.,;:!?'\"()/&@#+°–—]", re.UNICODE)


def sanitize(value: str, max_len: int = 500) -> str:
    """Strip control characters, limit length, and HTML-escape."""
    text = value[:max_len]
    text = _SAFE_TEXT.sub("", text)
    return html_mod.escape(text.strip())


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
for key, default in {
    "screen": 1,
    "intake_data": {},
    "analysis": None,
    "lawyer_decision": None,
    "premium": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <h1>AI Immigration Case Manager</h1>
    <p>Intelligent case preparation for Canadian immigration pathways</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Step indicator
# ---------------------------------------------------------------------------
def render_steps(current: int):
    labels = ["1. Client Intake", "2. AI Case Analysis", "3. Lawyer Review"]
    cols = st.columns([1, 3, 1])
    with cols[1]:
        parts = ['<div class="step-container">']
        for i, label in enumerate(labels, start=1):
            if i < current:
                cls = "step step-done"
            elif i == current:
                cls = "step step-active"
            else:
                cls = "step step-inactive"
            parts.append(f'<span class="{cls}">{label}</span>')
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)


render_steps(st.session_state.screen)


# ---------------------------------------------------------------------------
# Disclaimer helper (shown on every output screen)
# ---------------------------------------------------------------------------
def render_disclaimer():
    st.markdown(
        '<div class="disclaimer">'
        "<strong>Disclaimer:</strong> This is AI-generated analysis and does not "
        "constitute legal advice. Always consult a licensed immigration professional "
        "before taking any action."
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Usage badge helper
# ---------------------------------------------------------------------------
def render_usage_badge():
    if st.session_state.premium:
        st.markdown(
            '<span class="usage-badge">Premium — unlimited analyses</span>',
            unsafe_allow_html=True,
        )
    else:
        used = get_usage_count()
        remaining = max(FREE_ANALYSIS_LIMIT - used, 0)
        st.markdown(
            f'<span class="usage-badge">Free plan — {remaining} of '
            f"{FREE_ANALYSIS_LIMIT} analyses remaining</span>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Claude API helper
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert Canadian immigration paralegal assistant. Your role is to analyze client intake information and prepare a comprehensive case brief for a reviewing immigration lawyer.

Rules:
- Be conservative on eligibility — err on the side of flagging uncertainty.
- Never give direct legal advice. Frame everything as "the lawyer should consider" or "this may warrant further review."
- Return your analysis as valid JSON with the exact structure specified in the user message.
- Be thorough but concise. The lawyer reviewing this is experienced and values clarity over length.
- Focus only on these Canadian immigration pathways: Express Entry (Federal Skilled Worker), Spousal/Partner Sponsorship, Post-Graduate Work Permit, and Intra-Company Transfer (work permit).
- For the eligibility assessment, rank pathways by likelihood of success.
- Flag any inconsistencies or red flags an immigration officer might scrutinize."""


def run_analysis(intake: dict) -> dict | None:
    """Send intake data to Claude and return structured analysis."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error(
            "**Configuration error:** The API key is not set. "
            "Please contact the site administrator."
        )
        return None

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""Analyze the following immigration client intake and return a JSON object with this exact structure:

{{
  "eligibility_assessment": [
    {{
      "pathway": "<pathway name>",
      "likelihood": "<strong|moderate|weak|ineligible>",
      "reasoning": "<2-3 sentence explanation>"
    }}
  ],
  "recommended_pathway": {{
    "pathway": "<single best pathway>",
    "explanation": "<paragraph explaining why this is the best option>"
  }},
  "documents_checklist": [
    {{
      "document": "<document name>",
      "status": "<likely have|need to obtain|may be required>",
      "notes": "<brief context>"
    }}
  ],
  "risk_flags": [
    {{
      "flag": "<risk description>",
      "severity": "<high|medium|low>",
      "mitigation": "<what the lawyer should consider>"
    }}
  ],
  "estimated_timeline": [
    {{
      "milestone": "<milestone name>",
      "timeframe": "<estimated timeframe>",
      "notes": "<any caveats>"
    }}
  ],
  "case_summary": "<2-3 paragraph brief written for the reviewing lawyer>"
}}

Client intake data:
{json.dumps(intake, indent=2)}

Important: Return ONLY the JSON object, no markdown formatting, no code fences, no extra text."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        st.error(
            "We couldn't parse the AI response. Please try again — "
            "this is usually a one-time issue."
        )
        return None
    except anthropic.RateLimitError:
        st.error(
            "The service is experiencing high demand. "
            "Please wait a moment and try again."
        )
        return None
    except anthropic.AuthenticationError:
        st.error(
            "**Configuration error:** The API key is invalid. "
            "Please contact the site administrator."
        )
        return None
    except anthropic.APIError as exc:
        st.error(
            f"Something went wrong while generating your analysis. "
            f"Please try again. (Error: {exc.status_code})"
        )
        return None
    except Exception:
        st.error(
            "An unexpected error occurred. Please refresh the page and try again."
        )
        return None


# ===================================================================
# UPGRADE / PAYWALL SCREEN
# ===================================================================
def screen_upgrade():
    st.markdown(
        '<div class="upgrade-box">'
        "<h2>You've used your 3 free analyses</h2>"
        "<p>Upgrade to get unlimited AI-powered case analyses for your practice.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.link_button(
            "Upgrade — $19/month",
            STRIPE_CHECKOUT_URL,
            type="primary",
            use_container_width=True,
        )

        st.markdown("---")
        st.markdown("**Already upgraded?** Enter your access token below.")
        token_input = st.text_input(
            "Access token",
            type="password",
            placeholder="Paste the token from your confirmation email",
        )
        if st.button("Activate", use_container_width=True):
            if token_input and is_valid_token(token_input):
                st.session_state.premium = True
                st.success("Token accepted — you now have unlimited access.")
                st.rerun()
            else:
                st.error("Invalid token. Please check your email and try again.")


# ===================================================================
# SCREEN 1 — Client Intake Form
# ===================================================================
def screen_intake():
    render_usage_badge()

    st.subheader("Client Intake Form")
    st.caption("Complete all fields to generate an AI-powered case analysis.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### Personal Information")
        full_name = st.text_input("Full legal name", placeholder="e.g. Maria Santos")
        country_origin = st.text_input(
            "Country of origin", placeholder="e.g. Philippines"
        )
        country_residence = st.text_input(
            "Current country of residence", placeholder="e.g. Canada"
        )
        current_status = st.selectbox(
            "Current immigration status",
            [
                "",
                "Citizen of another country (outside Canada)",
                "Visitor",
                "Student (study permit)",
                "Worker (work permit)",
                "Temporary Resident",
                "Undocumented",
            ],
        )
        goal = st.selectbox(
            "Immigration goal",
            [
                "",
                "Express Entry (Canadian Permanent Residence)",
                "Spousal / Partner Sponsorship",
                "Study Permit",
                "Work Permit (LMIA-based)",
                "Intra-Company Transfer",
            ],
        )

    with col2:
        st.markdown("##### Qualifications & Background")
        education = st.selectbox(
            "Highest education level",
            [
                "",
                "High school",
                "1-year diploma/certificate",
                "2-year diploma",
                "Bachelor's degree",
                "Master's degree",
                "Doctorate (PhD)",
            ],
        )
        work_experience = st.slider("Years of work experience", 0, 30, 0)
        marital_status = st.selectbox(
            "Marital status",
            ["", "Single", "Married", "Common-law partner", "Divorced", "Widowed"],
        )
        spouse_canadian = st.selectbox(
            "Is your spouse/partner a Canadian citizen or PR?",
            ["", "Yes", "No", "N/A"],
        )

        st.markdown("##### Language Scores (IELTS — optional)")
        lc1, lc2, lc3, lc4 = st.columns(4)
        with lc1:
            ielts_listening = st.number_input(
                "Listening", min_value=0.0, max_value=9.0, step=0.5, value=0.0,
                format="%.1f",
            )
        with lc2:
            ielts_reading = st.number_input(
                "Reading", min_value=0.0, max_value=9.0, step=0.5, value=0.0,
                format="%.1f",
            )
        with lc3:
            ielts_writing = st.number_input(
                "Writing", min_value=0.0, max_value=9.0, step=0.5, value=0.0,
                format="%.1f",
            )
        with lc4:
            ielts_speaking = st.number_input(
                "Speaking", min_value=0.0, max_value=9.0, step=0.5, value=0.0,
                format="%.1f",
            )

    st.markdown("##### Visa History")
    prev_rejections = st.radio(
        "Any previous visa or permit rejections?", ["No", "Yes"], horizontal=True,
    )
    rejection_details = ""
    if prev_rejections == "Yes":
        rejection_details = st.text_area(
            "Please describe previous rejections",
            placeholder="e.g. Study permit refused in 2022 due to insufficient ties to home country",
        )

    st.markdown("---")

    if st.button(
        "Submit & Generate Case Analysis", type="primary", use_container_width=True
    ):
        # Validate required fields
        missing = []
        if not full_name.strip():
            missing.append("Full name")
        if not country_origin.strip():
            missing.append("Country of origin")
        if not country_residence.strip():
            missing.append("Current country of residence")
        if not current_status:
            missing.append("Current immigration status")
        if not goal:
            missing.append("Immigration goal")
        if not education:
            missing.append("Education level")
        if not marital_status:
            missing.append("Marital status")

        if missing:
            st.warning(f"Please fill in: {', '.join(missing)}")
            return

        # --- Usage limit check ---
        if not st.session_state.premium:
            if get_usage_count() >= FREE_ANALYSIS_LIMIT:
                st.session_state.screen = "upgrade"
                st.rerun()

        # Build intake dict with sanitized inputs
        ielts = None
        if any(
            v > 0
            for v in [ielts_listening, ielts_reading, ielts_writing, ielts_speaking]
        ):
            ielts = {
                "listening": ielts_listening,
                "reading": ielts_reading,
                "writing": ielts_writing,
                "speaking": ielts_speaking,
            }

        st.session_state.intake_data = {
            "full_name": sanitize(full_name),
            "country_of_origin": sanitize(country_origin),
            "country_of_residence": sanitize(country_residence),
            "current_immigration_status": sanitize(current_status),
            "immigration_goal": sanitize(goal),
            "education_level": sanitize(education),
            "years_of_work_experience": work_experience,
            "marital_status": sanitize(marital_status),
            "spouse_is_canadian_citizen_or_pr": sanitize(
                spouse_canadian if spouse_canadian else "N/A"
            ),
            "ielts_scores": ielts,
            "previous_visa_rejections": prev_rejections == "Yes",
            "rejection_details": (
                sanitize(rejection_details, max_len=1000)
                if rejection_details
                else None
            ),
        }

        # Run AI analysis with a detailed spinner
        with st.spinner("Analyzing your case — reviewing eligibility, documents, and risk factors..."):
            result = run_analysis(st.session_state.intake_data)

        if result:
            # Count the usage AFTER a successful analysis
            increment_usage()
            st.session_state.analysis = result
            st.session_state.screen = 2
            st.rerun()


# ===================================================================
# SCREEN 2 — AI Case Analysis
# ===================================================================
def screen_analysis():
    analysis = st.session_state.analysis
    intake = st.session_state.intake_data

    render_usage_badge()

    st.subheader(f"Case Analysis — {intake.get('full_name', 'Client')}")
    st.caption(
        f"Goal: {intake.get('immigration_goal', '')}  |  "
        f"Status: {intake.get('current_immigration_status', '')}"
    )

    # --- Eligibility Assessment ---
    st.markdown("### Eligibility Assessment")
    for item in analysis.get("eligibility_assessment", []):
        likelihood = item.get("likelihood", "").lower()
        if likelihood == "strong":
            css_class, badge, badge_color = "risk-green", "Strong", "#4CAF50"
        elif likelihood == "moderate":
            css_class, badge, badge_color = "risk-yellow", "Moderate", "#FFC107"
        else:
            css_class = "risk-red"
            badge = likelihood.capitalize()
            badge_color = "#F44336"

        st.markdown(
            f"""<div class="{css_class}">
            <strong>{html_mod.escape(item.get('pathway', ''))}</strong>
            &nbsp;<span style="background:{badge_color};color:white;padding:2px 8px;
            border-radius:10px;font-size:0.75rem;">{badge}</span>
            <br><span style="color:#555;">{html_mod.escape(item.get('reasoning', ''))}</span>
            </div>""",
            unsafe_allow_html=True,
        )

    # --- Recommended Pathway ---
    rec = analysis.get("recommended_pathway", {})
    if rec:
        st.markdown("### Recommended Pathway")
        st.success(f"**{html_mod.escape(rec.get('pathway', ''))}**")
        st.markdown(html_mod.escape(rec.get("explanation", "")))

    # --- Documents Checklist ---
    st.markdown("### Required Documents Checklist")
    for doc in analysis.get("documents_checklist", []):
        status = doc.get("status", "").lower()
        if "have" in status and "need" not in status:
            icon = "&#9989;"
        elif "need" in status:
            icon = "&#10060;"
        else:
            icon = "&#9888;&#65039;"
        line = (
            f"{icon} **{html_mod.escape(doc.get('document', ''))}** "
            f"— _{html_mod.escape(doc.get('status', ''))}_"
        )
        if doc.get("notes"):
            line += (
                f"  \n<small style='color:#777;'>"
                f"{html_mod.escape(doc['notes'])}</small>"
            )
        st.markdown(line, unsafe_allow_html=True)

    # --- Risk Flags ---
    st.markdown("### Risk Flags")
    flags = analysis.get("risk_flags", [])
    if flags:
        for flag in flags:
            severity = flag.get("severity", "").lower()
            if severity == "high":
                css_class = "risk-red"
            elif severity == "medium":
                css_class = "risk-yellow"
            else:
                css_class = "risk-green"
            st.markdown(
                f"""<div class="{css_class}">
                <strong>{html_mod.escape(flag.get('flag', ''))}</strong>
                <em>({severity} severity)</em><br>
                <span style="color:#555;">Mitigation:
                {html_mod.escape(flag.get('mitigation', ''))}</span>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.info("No significant risk flags identified.")

    # --- Estimated Timeline ---
    st.markdown("### Estimated Timeline")
    for step in analysis.get("estimated_timeline", []):
        line = (
            f"**{html_mod.escape(step.get('milestone', ''))}** — "
            f"{html_mod.escape(step.get('timeframe', ''))}"
        )
        if step.get("notes"):
            line += (
                f"  \n<small style='color:#777;'>"
                f"{html_mod.escape(step['notes'])}</small>"
            )
        st.markdown(line, unsafe_allow_html=True)

    # --- Case Summary ---
    st.markdown("### Case Summary")
    st.markdown(
        f'<div class="section-card">'
        f"{html_mod.escape(analysis.get('case_summary', ''))}</div>",
        unsafe_allow_html=True,
    )

    render_disclaimer()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "Proceed to Lawyer Review", type="primary", use_container_width=True
        ):
            st.session_state.screen = 3
            st.rerun()
    with col2:
        if st.button("Start Over", use_container_width=True):
            st.session_state.screen = 1
            st.session_state.analysis = None
            st.session_state.intake_data = {}
            st.session_state.lawyer_decision = None
            st.rerun()


# ===================================================================
# SCREEN 3 — Lawyer Review Panel
# ===================================================================
def screen_lawyer_review():
    analysis = st.session_state.analysis
    intake = st.session_state.intake_data

    st.subheader("Lawyer Review Panel")
    st.caption("Review the AI-generated case brief below and take action.")

    # --- Client snapshot ---
    st.markdown("#### Client Overview")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**Name:** {html_mod.escape(intake.get('full_name', ''))}")
        st.markdown(f"**Origin:** {html_mod.escape(intake.get('country_of_origin', ''))}")
        st.markdown(f"**Residence:** {html_mod.escape(intake.get('country_of_residence', ''))}")
    with c2:
        st.markdown(f"**Status:** {html_mod.escape(intake.get('current_immigration_status', ''))}")
        st.markdown(f"**Goal:** {html_mod.escape(intake.get('immigration_goal', ''))}")
        st.markdown(f"**Education:** {html_mod.escape(intake.get('education_level', ''))}")
    with c3:
        st.markdown(f"**Experience:** {intake.get('years_of_work_experience', 0)} years")
        st.markdown(f"**Marital status:** {html_mod.escape(intake.get('marital_status', ''))}")
        st.markdown(
            f"**Spouse CDN/PR:** "
            f"{html_mod.escape(intake.get('spouse_is_canadian_citizen_or_pr', 'N/A'))}"
        )

    if intake.get("ielts_scores"):
        ielts = intake["ielts_scores"]
        st.markdown(
            f"**IELTS:** L {ielts['listening']} | R {ielts['reading']} "
            f"| W {ielts['writing']} | S {ielts['speaking']}"
        )
    if intake.get("previous_visa_rejections"):
        st.warning(
            f"Previous rejections: "
            f"{html_mod.escape(intake.get('rejection_details') or 'Details not provided')}"
        )

    st.markdown("---")

    # --- Recommended Pathway ---
    rec = analysis.get("recommended_pathway", {})
    if rec:
        st.markdown("#### Recommended Pathway")
        st.success(f"**{html_mod.escape(rec.get('pathway', ''))}**")
        st.markdown(html_mod.escape(rec.get("explanation", "")))

    # --- Eligibility (compact) ---
    st.markdown("#### Eligibility Assessment")
    for item in analysis.get("eligibility_assessment", []):
        likelihood = item.get("likelihood", "").lower()
        if likelihood == "strong":
            badge_color = "#4CAF50"
        elif likelihood == "moderate":
            badge_color = "#FFC107"
        else:
            badge_color = "#F44336"
        st.markdown(
            f'<span style="background:{badge_color};color:white;padding:2px 8px;'
            f'border-radius:10px;font-size:0.75rem;">{likelihood.capitalize()}</span> '
            f'**{html_mod.escape(item.get("pathway", ""))}** — '
            f'{html_mod.escape(item.get("reasoning", ""))}',
            unsafe_allow_html=True,
        )

    # --- Risk Flags ---
    st.markdown("#### Risk Flags")
    flags = analysis.get("risk_flags", [])
    if flags:
        for flag in flags:
            severity = flag.get("severity", "").lower()
            if severity == "high":
                color = "#F44336"
            elif severity == "medium":
                color = "#FFC107"
            else:
                color = "#4CAF50"
            st.markdown(
                f'<span style="color:{color};font-weight:bold;">[{severity.upper()}]</span> '
                f'{html_mod.escape(flag.get("flag", ""))} — '
                f'{html_mod.escape(flag.get("mitigation", ""))}',
                unsafe_allow_html=True,
            )
    else:
        st.info("No significant risk flags identified.")

    # --- Documents ---
    st.markdown("#### Documents Checklist")
    for doc in analysis.get("documents_checklist", []):
        status = doc.get("status", "").lower()
        if "have" in status and "need" not in status:
            icon = "&#9989;"
        elif "need" in status:
            icon = "&#10060;"
        else:
            icon = "&#9888;&#65039;"
        st.markdown(
            f"{icon} {html_mod.escape(doc.get('document', ''))} — "
            f"_{html_mod.escape(doc.get('status', ''))}_",
            unsafe_allow_html=True,
        )

    # --- Timeline ---
    st.markdown("#### Estimated Timeline")
    for step in analysis.get("estimated_timeline", []):
        st.markdown(
            f"- **{html_mod.escape(step.get('milestone', ''))}** — "
            f"{html_mod.escape(step.get('timeframe', ''))}"
        )

    # --- Case Summary ---
    st.markdown("#### Case Summary")
    st.markdown(
        f'<div class="section-card">'
        f"{html_mod.escape(analysis.get('case_summary', ''))}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # --- Lawyer actions ---
    if st.session_state.lawyer_decision:
        decision = st.session_state.lawyer_decision
        if decision["action"] == "approved":
            st.success(
                "This case brief has been **approved**. The file is ready for processing."
            )
        else:
            st.warning("This case has been **flagged for manual review**.")
            st.markdown(
                f"**Lawyer notes:** {html_mod.escape(decision.get('notes', 'None'))}"
            )

        if st.button("Start New Case", use_container_width=True):
            st.session_state.screen = 1
            st.session_state.analysis = None
            st.session_state.intake_data = {}
            st.session_state.lawyer_decision = None
            st.rerun()
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Approve Case Brief", type="primary", use_container_width=True
            ):
                st.session_state.lawyer_decision = {"action": "approved"}
                st.rerun()
        with col2:
            flag_notes = st.text_area(
                "Notes for manual review",
                placeholder="Describe concerns or additional steps needed...",
            )
            if st.button("Flag for Manual Review", use_container_width=True):
                st.session_state.lawyer_decision = {
                    "action": "flagged",
                    "notes": sanitize(flag_notes, max_len=2000) or "No notes provided.",
                }
                st.rerun()

    render_disclaimer()


# ===================================================================
# Router
# ===================================================================
if st.session_state.screen == "upgrade":
    screen_upgrade()
elif st.session_state.screen == 1:
    screen_intake()
elif st.session_state.screen == 2:
    screen_analysis()
elif st.session_state.screen == 3:
    screen_lawyer_review()
