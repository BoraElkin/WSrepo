# AI Immigration Case Manager

An AI-powered immigration case preparation engine built with Streamlit and Claude. Designed for the Wealthsimple AI Builder application.

## How It Works

1. **Client Intake** — A client fills out a structured intake form with personal, immigration, and qualification details.
2. **AI Case Analysis** — Claude analyzes the intake and produces a full case brief: eligibility rankings, document checklists, risk flags, recommended pathway, timeline, and a lawyer-ready summary.
3. **Lawyer Review** — A lawyer reviews the AI-generated brief and either approves it or flags it for manual review.

## Canadian Immigration Pathways Covered

- Express Entry (Federal Skilled Worker)
- Spousal / Partner Sponsorship
- Post-Graduate Work Permit
- Intra-Company Transfer (Work Permit)

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create a .env file with your API key
cp .env.example .env
# Edit .env and add your Anthropic API key

# 3. Run the app
streamlit run app.py
```

## Tech Stack

- **Python + Streamlit** — UI and session management
- **Anthropic Claude API** — AI analysis engine (claude-opus-4-6)
- **python-dotenv** — Environment variable management

## Disclaimer

This tool is for demonstration purposes. All AI-generated analysis must be reviewed by a licensed immigration professional before any action is taken.
