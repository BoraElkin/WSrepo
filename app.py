import os
import json
import streamlit as st
from dotenv import load_dotenv
import anthropic

load_dotenv()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Immigration Case Manager",
    page_icon="🍁",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS for polished look
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
    .section-card h3 {
        margin-top: 0;
    }

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

    /* Hide default streamlit padding at top */
    .block-container {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "screen" not in st.session_state:
    st.session_state.screen = 1
if "intake_data" not in st.session_state:
    st.session_state.intake_data = {}
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "lawyer_decision" not in st.session_state:
    st.session_state.lawyer_decision = None

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
        html_parts = ['<div class="step-container">']
        for i, label in enumerate(labels, start=1):
            if i < current:
                cls = "step step-done"
            elif i == current:
                cls = "step step-active"
            else:
                cls = "step step-inactive"
            html_parts.append(f'<span class="{cls}">{label}</span>')
        html_parts.append("</div>")
        st.markdown("".join(html_parts), unsafe_allow_html=True)

render_steps(st.session_state.screen)

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
        st.error("ANTHROPIC_API_KEY not found. Add it to your .env file.")
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
        st.error("Failed to parse AI response. Please try again.")
        return None
    except anthropic.APIError as e:
        st.error(f"API error: {e}")
        return None


# ===================================================================
# SCREEN 1 — Client Intake Form
# ===================================================================
def screen_intake():
    st.subheader("Client Intake Form")
    st.caption("Complete all fields to generate an AI-powered case analysis.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### Personal Information")
        full_name = st.text_input("Full legal name", placeholder="e.g. Maria Santos")
        country_origin = st.text_input("Country of origin", placeholder="e.g. Philippines")
        country_residence = st.text_input("Current country of residence", placeholder="e.g. Canada")
        current_status = st.selectbox(
            "Current immigration status",
            ["", "Citizen of another country (outside Canada)", "Visitor", "Student (study permit)", "Worker (work permit)", "Temporary Resident", "Undocumented"],
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
            ["", "High school", "1-year diploma/certificate", "2-year diploma", "Bachelor's degree", "Master's degree", "Doctorate (PhD)"],
        )
        work_experience = st.slider("Years of work experience", 0, 30, 0)
        marital_status = st.selectbox("Marital status", ["", "Single", "Married", "Common-law partner", "Divorced", "Widowed"])
        spouse_canadian = st.selectbox("Is your spouse/partner a Canadian citizen or PR?", ["", "Yes", "No", "N/A"])

        st.markdown("##### Language Scores (IELTS — optional)")
        lc1, lc2, lc3, lc4 = st.columns(4)
        with lc1:
            ielts_listening = st.number_input("Listening", min_value=0.0, max_value=9.0, step=0.5, value=0.0, format="%.1f")
        with lc2:
            ielts_reading = st.number_input("Reading", min_value=0.0, max_value=9.0, step=0.5, value=0.0, format="%.1f")
        with lc3:
            ielts_writing = st.number_input("Writing", min_value=0.0, max_value=9.0, step=0.5, value=0.0, format="%.1f")
        with lc4:
            ielts_speaking = st.number_input("Speaking", min_value=0.0, max_value=9.0, step=0.5, value=0.0, format="%.1f")

    st.markdown("##### Visa History")
    prev_rejections = st.radio("Any previous visa or permit rejections?", ["No", "Yes"], horizontal=True)
    rejection_details = ""
    if prev_rejections == "Yes":
        rejection_details = st.text_area("Please describe previous rejections", placeholder="e.g. Study permit refused in 2022 due to insufficient ties to home country")

    st.markdown("---")

    if st.button("Submit & Generate Case Analysis", type="primary", use_container_width=True):
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

        # Build intake dict
        ielts = None
        if any(v > 0 for v in [ielts_listening, ielts_reading, ielts_writing, ielts_speaking]):
            ielts = {
                "listening": ielts_listening,
                "reading": ielts_reading,
                "writing": ielts_writing,
                "speaking": ielts_speaking,
            }

        st.session_state.intake_data = {
            "full_name": full_name.strip(),
            "country_of_origin": country_origin.strip(),
            "country_of_residence": country_residence.strip(),
            "current_immigration_status": current_status,
            "immigration_goal": goal,
            "education_level": education,
            "years_of_work_experience": work_experience,
            "marital_status": marital_status,
            "spouse_is_canadian_citizen_or_pr": spouse_canadian if spouse_canadian else "N/A",
            "ielts_scores": ielts,
            "previous_visa_rejections": prev_rejections == "Yes",
            "rejection_details": rejection_details.strip() if rejection_details else None,
        }

        # Run AI analysis
        with st.spinner("Analyzing case with AI — this may take a moment..."):
            result = run_analysis(st.session_state.intake_data)

        if result:
            st.session_state.analysis = result
            st.session_state.screen = 2
            st.rerun()


# ===================================================================
# SCREEN 2 — AI Case Analysis
# ===================================================================
def screen_analysis():
    analysis = st.session_state.analysis
    intake = st.session_state.intake_data

    st.subheader(f"Case Analysis — {intake.get('full_name', 'Client')}")
    st.caption(f"Goal: {intake.get('immigration_goal', '')}  |  Status: {intake.get('current_immigration_status', '')}")

    # --- Eligibility Assessment ---
    st.markdown("### Eligibility Assessment")
    for item in analysis.get("eligibility_assessment", []):
        likelihood = item.get("likelihood", "").lower()
        if likelihood == "strong":
            css_class = "risk-green"
            badge = "Strong"
            badge_color = "#4CAF50"
        elif likelihood == "moderate":
            css_class = "risk-yellow"
            badge = "Moderate"
            badge_color = "#FFC107"
        else:
            css_class = "risk-red"
            badge = likelihood.capitalize()
            badge_color = "#F44336"

        st.markdown(
            f"""<div class="{css_class}">
            <strong>{item.get('pathway', '')}</strong>
            &nbsp;<span style="background:{badge_color};color:white;padding:2px 8px;border-radius:10px;font-size:0.75rem;">{badge}</span>
            <br><span style="color:#555;">{item.get('reasoning', '')}</span>
            </div>""",
            unsafe_allow_html=True,
        )

    # --- Recommended Pathway ---
    rec = analysis.get("recommended_pathway", {})
    if rec:
        st.markdown("### Recommended Pathway")
        st.success(f"**{rec.get('pathway', '')}**")
        st.markdown(rec.get("explanation", ""))

    # --- Documents Checklist ---
    st.markdown("### Required Documents Checklist")
    docs = analysis.get("documents_checklist", [])
    if docs:
        for doc in docs:
            status = doc.get("status", "").lower()
            if "have" in status and "need" not in status:
                icon = "&#9989;"  # green check
            elif "need" in status:
                icon = "&#10060;"  # red cross
            else:
                icon = "&#9888;&#65039;"  # warning
            st.markdown(
                f"{icon} **{doc.get('document', '')}** — _{doc.get('status', '')}_"
                + (f"  \n<small style='color:#777;'>{doc.get('notes', '')}</small>" if doc.get("notes") else ""),
                unsafe_allow_html=True,
            )

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
                <strong>{flag.get('flag', '')}</strong> <em>({severity} severity)</em><br>
                <span style="color:#555;">Mitigation: {flag.get('mitigation', '')}</span>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.info("No significant risk flags identified.")

    # --- Estimated Timeline ---
    st.markdown("### Estimated Timeline")
    timeline = analysis.get("estimated_timeline", [])
    if timeline:
        for step in timeline:
            st.markdown(
                f"**{step.get('milestone', '')}** — {step.get('timeframe', '')}"
                + (f"  \n<small style='color:#777;'>{step.get('notes', '')}</small>" if step.get("notes") else ""),
                unsafe_allow_html=True,
            )

    # --- Case Summary ---
    st.markdown("### Case Summary")
    st.markdown(
        f"""<div class="section-card">{analysis.get('case_summary', '')}</div>""",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Proceed to Lawyer Review", type="primary", use_container_width=True):
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
        st.markdown(f"**Name:** {intake.get('full_name', '')}")
        st.markdown(f"**Origin:** {intake.get('country_of_origin', '')}")
        st.markdown(f"**Residence:** {intake.get('country_of_residence', '')}")
    with c2:
        st.markdown(f"**Status:** {intake.get('current_immigration_status', '')}")
        st.markdown(f"**Goal:** {intake.get('immigration_goal', '')}")
        st.markdown(f"**Education:** {intake.get('education_level', '')}")
    with c3:
        st.markdown(f"**Experience:** {intake.get('years_of_work_experience', 0)} years")
        st.markdown(f"**Marital status:** {intake.get('marital_status', '')}")
        st.markdown(f"**Spouse CDN/PR:** {intake.get('spouse_is_canadian_citizen_or_pr', 'N/A')}")

    if intake.get("ielts_scores"):
        ielts = intake["ielts_scores"]
        st.markdown(
            f"**IELTS:** L {ielts['listening']} | R {ielts['reading']} | W {ielts['writing']} | S {ielts['speaking']}"
        )
    if intake.get("previous_visa_rejections"):
        st.warning(f"Previous rejections: {intake.get('rejection_details', 'Details not provided')}")

    st.markdown("---")

    # --- Recommended Pathway ---
    rec = analysis.get("recommended_pathway", {})
    if rec:
        st.markdown("#### Recommended Pathway")
        st.success(f"**{rec.get('pathway', '')}**")
        st.markdown(rec.get("explanation", ""))

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
            f'<span style="background:{badge_color};color:white;padding:2px 8px;border-radius:10px;font-size:0.75rem;">'
            f'{likelihood.capitalize()}</span> **{item.get("pathway", "")}** — {item.get("reasoning", "")}',
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
                f'{flag.get("flag", "")} — {flag.get("mitigation", "")}',
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
        st.markdown(f"{icon} {doc.get('document', '')} — _{doc.get('status', '')}_", unsafe_allow_html=True)

    # --- Timeline ---
    st.markdown("#### Estimated Timeline")
    for step in analysis.get("estimated_timeline", []):
        st.markdown(f"- **{step.get('milestone', '')}** — {step.get('timeframe', '')}")

    # --- Case Summary ---
    st.markdown("#### Case Summary")
    st.markdown(
        f"""<div class="section-card">{analysis.get('case_summary', '')}</div>""",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # --- Lawyer actions ---
    if st.session_state.lawyer_decision:
        decision = st.session_state.lawyer_decision
        if decision["action"] == "approved":
            st.success("This case brief has been **approved**. The file is ready for processing.")
        else:
            st.warning("This case has been **flagged for manual review**.")
            st.markdown(f"**Lawyer notes:** {decision.get('notes', 'None')}")

        if st.button("Start New Case", use_container_width=True):
            st.session_state.screen = 1
            st.session_state.analysis = None
            st.session_state.intake_data = {}
            st.session_state.lawyer_decision = None
            st.rerun()
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve Case Brief", type="primary", use_container_width=True):
                st.session_state.lawyer_decision = {"action": "approved"}
                st.rerun()
        with col2:
            flag_notes = st.text_area("Notes for manual review", placeholder="Describe concerns or additional steps needed...")
            if st.button("Flag for Manual Review", use_container_width=True):
                st.session_state.lawyer_decision = {
                    "action": "flagged",
                    "notes": flag_notes.strip() or "No notes provided.",
                }
                st.rerun()

    # --- Disclaimer ---
    st.markdown(
        '<div class="disclaimer">'
        "<strong>Disclaimer:</strong> This analysis is AI-generated and must be reviewed by a licensed "
        "immigration professional before any action is taken. It does not constitute legal advice."
        "</div>",
        unsafe_allow_html=True,
    )


# ===================================================================
# Router
# ===================================================================
if st.session_state.screen == 1:
    screen_intake()
elif st.session_state.screen == 2:
    screen_analysis()
elif st.session_state.screen == 3:
    screen_lawyer_review()
