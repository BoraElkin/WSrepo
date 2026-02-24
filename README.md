# AI Immigration Case Manager

An AI-powered immigration case preparation engine built with Streamlit and Claude.

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
# 1. Clone the repo
git clone <repo-url>
cd WSrepo

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install pinned dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and add your Anthropic API key

# 5. Run the app
streamlit run app.py
```

The app will open at `http://localhost:8501`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `STRIPE_CHECKOUT_URL` | No | Stripe checkout link (defaults to placeholder) |

## Usage Limits & Payments

- Free users get **3 case analyses** per IP address, tracked in a local SQLite database (`usage.db`).
- After 3 uses, users see an upgrade screen with a Stripe checkout link.
- Paid users enter an **access token** to bypass the limit. Tokens are stored in `valid_tokens.txt` (one per line).
- Generate a token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

## Security

- API key is loaded exclusively from environment variables — never hardcoded.
- All user inputs are sanitized (length-limited, control characters stripped, HTML-escaped) before being sent to the API or rendered.
- AI outputs are HTML-escaped before rendering to prevent XSS.
- A legal disclaimer appears on every output screen.
- IP addresses are SHA-256 hashed before storage — raw IPs are never persisted.

## Tech Stack

- **Python + Streamlit** — UI, session management, responsive layout
- **Anthropic Claude API** — AI analysis engine (`claude-opus-4-6`)
- **SQLite** — Lightweight usage tracking (no external database needed)
- **python-dotenv** — Environment variable management

## Deployment

The app is ready for deployment on any platform that supports Streamlit:

- **Streamlit Community Cloud** — Connect the repo and set `ANTHROPIC_API_KEY` in the Secrets panel.
- **Railway / Render / Fly.io** — Deploy with `streamlit run app.py` as the start command.
- **Docker** — Use `python:3.11-slim` as the base image, install requirements, expose port 8501.

## Disclaimer

This tool is for demonstration purposes. All AI-generated analysis must be reviewed by a licensed immigration professional before any action is taken. It does not constitute legal advice.
