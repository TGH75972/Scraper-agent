# Scrapem

Scrapem is an autonomous market intelligence agent that monitors live web news, evaluates which stories matter for a business, and produces an executive briefing with ranked signals, strategic recommendations, and optional Discord alerts.

It combines:
- Live news discovery via Google News RSS
- Article extraction and metadata scraping
- Structured competitive analysis using Groq models
- A lightweight web UI for running sweeps and reviewing results
- A cron endpoint for scheduled monitoring

## Features

- Topic-driven news discovery for any market or strategic theme
- Business-specific analysis tailored to a company profile and analyst directive
- Impact scoring from 0-100 with urgency and sentiment classification
- Automated competitor, trend, driver, risk, and recommendation synthesis
- Signal ranking with article-level relevance and rationale
- Built-in history tracking so the agent can compare current runs against prior intelligence
- Optional Discord webhook notifications for high-impact alerts
- Deployed as a Python Flask app with static frontend assets

## Tech Stack

- Python 3
- Flask
- Requests
- BeautifulSoup
- feedparser
- Groq API
- Vercel-ready deployment configuration

## Project Structure

```text
.
├── api/
│   └── index.py           # Flask backend, scraping logic, Groq analysis, cron routes
├── public/
│   ├── index.html         # Frontend shell
│   ├── script.js          # UI logic and API calls
│   └── style.css          # Styling for the market intelligence dashboard
├── .env.example           # Environment variable template
├── .gitignore
├── requirements.txt       # Python dependencies
├── vercel.json            # Vercel routing and cron config
└── README.md              # Project documentation
```

## Prerequisites

- Python 3.10+
- A Groq API key
- Optional: Discord webhook URL for alerting

## Setup

1. Clone the repository.
2. Create a virtual environment and install dependencies.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. Copy the example environment file and fill in your values.

```bash
cp .env.example .env
```

Example values:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
DISCORD_WEBHOOK_URL=your_discord_webhook_url
TARGET_TOPIC=AI startup funding
BUSINESS_PROFILE=B2B SaaS startup building AI marketing tools
ALERT_THRESHOLD=75
MAX_ARTICLES=6
CRON_SECRET=
```

## Run Locally

Start the Flask app:

```bash
python api/index.py
```

Then open:

```text
http://localhost:5000/
```

The web interface lets you:
- enter a business profile
- choose a signal topic
- add a custom analysis directive
- run a live sweep
- review ranked story insights and historical runs

## API Endpoints

### POST /api/analyze

Runs a discovery and analysis cycle for a provided topic and business profile.

Request body:

```json
{
  "topic": "AI startup funding",
  "profile": "B2B SaaS startup building AI marketing tools",
  "custom_prompt": "Prioritize competitive threats, funding momentum, and shifts that change go-to-market strategy."
}
```

Response includes:
- `meta` with run metadata
- `analysis` with headline summary, sentiment, risk profile, and recommendations
- `articles` sorted by relevance and classification
- `timeline` of prior runs

### GET /api/history

Returns the saved historical intelligence runs.

### GET /api/health

Returns service health and Groq configuration status.

### GET/POST /api/cron

Runs the default topic sweep for scheduled monitoring. It supports optional bearer auth via `CRON_SECRET`.

## Deployment

This repository is configured for Vercel via `vercel.json`.

### Vercel configuration

The app uses:
- `api/index.py` as the Python serverless function
- `public/**/*` as static frontend assets
- route mapping for `/api/*` and root page delivery
- a daily cron job at `0 8 * * *`

### Deploying to Vercel

1. Push the repo to GitHub
2. Import it into Vercel
3. Set environment variables in the Vercel project settings
4. Deploy

## Notes

- The app depends on live web access and Google News RSS; results may vary depending on source availability.
- `GROQ_API_KEY` is required for AI-powered analysis.
- High-impact runs can dispatch alerts to Discord when `DISCORD_WEBHOOK_URL` is configured and the impact score exceeds the threshold.
- The app stores prior run history in a temporary JSON file for the local environment.

## License

This project does not currently declare a license in the repository metadata. If you plan to publish or redistribute it, add an appropriate open-source license before doing so.

## Summary

Scrapem is a practical AI-powered competitive intelligence tool built for monitoring niche market shifts, evaluating strategic relevance, and turning noisy web data into actionable executive insight.
