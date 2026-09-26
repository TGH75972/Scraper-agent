import os
import re
import json
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from groq import Groq

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TARGET_TOPIC = os.environ.get("TARGET_TOPIC", "AI startup funding")
BUSINESS_PROFILE = os.environ.get("BUSINESS_PROFILE", "B2B SaaS startup building AI marketing tools")
CRON_SECRET = os.environ.get("CRON_SECRET", "")
ALERT_THRESHOLD = int(os.environ.get("ALERT_THRESHOLD", "75") or 75)
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "6") or 6)
HISTORY_LIMIT = 12
HISTORY_PATH = os.path.join(tempfile.gettempdir(), "market_intel_history.json")

STRATEGIC_TAGS = [
    "Market Threat",
    "Competitor Expansion",
    "Consumer Sentiment",
    "Funding Signal",
    "Product Launch",
    "Partnership",
    "Regulatory Shift",
    "Talent Movement",
    "Neutral Signal",
]

app = Flask(__name__, static_folder="../public", static_url_path="")


def get_client():
    if not GROQ_API_KEY:
        return None
    return Groq(api_key=GROQ_API_KEY)


def build_feed_url(topic):
    query = urllib.parse.quote(topic.strip() or TARGET_TOPIC)
    return f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


def strip_html(raw):
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def split_title_source(title):
    if not title:
        return "Untitled", ""
    parts = title.rsplit(" - ", 1)
    if len(parts) == 2 and 0 < len(parts[1]) <= 60:
        return parts[0].strip(), parts[1].strip()
    return title.strip(), ""


def domain_of(url):
    try:
        netloc = urllib.parse.urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def discover_entries(topic, limit):
    feed = feedparser.parse(build_feed_url(topic))
    entries = []
    for entry in feed.entries[:limit]:
        raw_title = entry.get("title", "")
        clean_title, derived_source = split_title_source(raw_title)
        source = ""
        source_field = entry.get("source")
        if source_field is not None:
            source = getattr(source_field, "title", "") or (source_field.get("title", "") if hasattr(source_field, "get") else "")
        entries.append({
            "title": clean_title,
            "google_url": entry.get("link", ""),
            "published": entry.get("published", ""),
            "source": source or derived_source or "News",
            "snippet": strip_html(entry.get("summary", ""))[:400],
        })
    return entries


def parse_batchexecute(text):
    for part in text.split("\n\n"):
        part = part.strip()
        if not part.startswith("["):
            continue
        try:
            outer = json.loads(part)
        except Exception:
            continue
        for row in outer:
            if isinstance(row, list) and len(row) > 2 and isinstance(row[2], str) and row[2].startswith("["):
                try:
                    inner = json.loads(row[2])
                except Exception:
                    continue
                if isinstance(inner, list) and len(inner) > 1 and isinstance(inner[1], str) and inner[1].startswith("http"):
                    return inner[1]
    return None


def resolve_article_url(google_url, timeout=10):
    if "/articles/" not in google_url:
        return google_url if google_url.startswith("http") and "news.google.com" not in google_url else None
    try:
        landing = requests.get(google_url, headers=BROWSER_HEADERS, timeout=timeout)
        soup = BeautifulSoup(landing.text, "html.parser")
        node = soup.select_one("c-wiz > div")
        if node is None:
            return None
        signature = node.get("data-n-a-sg")
        timestamp = node.get("data-n-a-ts")
        if not signature or not timestamp:
            return None
        article_id = google_url.split("/articles/")[1].split("?")[0]
        request_payload = [
            "garturlreq",
            [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
            article_id,
            int(timestamp),
            signature,
        ]
        envelope = [[["Fbv4je", json.dumps(request_payload), None, "generic"]]]
        body = "f.req=" + urllib.parse.quote(json.dumps(envelope))
        headers = dict(BROWSER_HEADERS)
        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        response = requests.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            data=body,
            headers=headers,
            timeout=timeout,
        )
        return parse_batchexecute(response.text)
    except Exception:
        return None


def meta_content(soup, *names):
    for name in names:
        tag = soup.find("meta", property=name) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def scrape_metadata(url, timeout=10):
    result = {"image": "", "description": "", "content": "", "resolved_title": ""}
    try:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
        if response.status_code >= 400:
            return result
        soup = BeautifulSoup(response.text, "html.parser")
        result["resolved_title"] = meta_content(soup, "og:title", "twitter:title") or (soup.title.string.strip() if soup.title and soup.title.string else "")
        result["image"] = meta_content(soup, "og:image", "twitter:image", "twitter:image:src") or ""
        result["description"] = meta_content(soup, "og:description", "twitter:description", "description") or ""
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        body = " ".join(p for p in paragraphs if len(p) > 40)
        result["content"] = re.sub(r"\s+", " ", body)[:1800]
    except Exception:
        pass
    return result


def build_article(entry):
    real_url = resolve_article_url(entry["google_url"])
    link = real_url or entry["google_url"]
    scraped = scrape_metadata(real_url) if real_url else {"image": "", "description": "", "content": "", "resolved_title": ""}
    source = entry["source"]
    site = domain_of(real_url) if real_url else ""
    if (not source or source == "News") and site:
        source = site
    context = scraped["content"] or scraped["description"] or entry["snippet"]
    return {
        "title": entry["title"] or scraped["resolved_title"] or "Untitled",
        "url": link,
        "source": source,
        "domain": site,
        "published": entry["published"],
        "image": scraped["image"],
        "snippet": scraped["description"] or entry["snippet"],
        "context": context[:1800],
    }


def gather_articles(topic, limit):
    entries = discover_entries(topic, limit)
    if not entries:
        return []
    articles = [None] * len(entries)
    with ThreadPoolExecutor(max_workers=min(8, len(entries))) as pool:
        futures = {pool.submit(build_article, entry): idx for idx, entry in enumerate(entries)}
        for future in futures:
            idx = futures[future]
            try:
                articles[idx] = future.result()
            except Exception:
                entry = entries[idx]
                articles[idx] = {
                    "title": entry["title"],
                    "url": entry["google_url"],
                    "source": entry["source"],
                    "domain": "",
                    "published": entry["published"],
                    "image": "",
                    "snippet": entry["snippet"],
                    "context": entry["snippet"],
                }
    return [a for a in articles if a]


def load_history():
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(record):
    try:
        history = load_history()
        history.insert(0, record)
        with open(HISTORY_PATH, "w", encoding="utf-8") as handle:
            json.dump(history[:HISTORY_LIMIT], handle)
    except Exception:
        pass


def history_for_topic(history, topic):
    key = topic.strip().lower()
    return [item for item in history if item.get("topic", "").strip().lower() == key]


def build_prompt(articles, profile, topic, custom_prompt, prior):
    sources = []
    for idx, article in enumerate(articles):
        sources.append({
            "index": idx,
            "title": article["title"],
            "source": article["source"],
            "published": article["published"],
            "content": article["context"] or article["snippet"],
        })
    prior_block = "None. Treat this as the first tracked run for this topic."
    if prior:
        prior_block = json.dumps(prior[:5])
    directive = custom_prompt.strip() or "Prioritize competitive threats, funding momentum, and shifts that change go-to-market strategy."
    return f"""You are an autonomous market intelligence analyst for the following business.

BUSINESS PROFILE: {profile}
MONITORED TOPIC: {topic}
ANALYST DIRECTIVE: {directive}

PRIOR INTELLIGENCE (previous runs, newest first):
{prior_block}

CURRENT SIGNALS (scraped from live news, referenced by index):
{json.dumps(sources, ensure_ascii=False)}

Classify each signal, quantify its impact on THIS business, reason about why it matters, and synthesize an executive briefing. Compare against prior intelligence to describe how the competitive landscape is evolving.

Allowed classification values: {json.dumps(STRATEGIC_TAGS)}

Return only valid JSON with this exact schema and no commentary:
{{
  "headline_summary": "2-3 sentence executive briefing",
  "category": "dominant strategic theme",
  "impact_score": 0,
  "sentiment": "Positive | Neutral | Negative | Mixed",
  "urgency": "Low | Medium | High",
  "evolution_note": "how this compares to prior intelligence",
  "competitor_analysis": [
    {{"name": "string", "threat_level": "High | Medium | Low", "activity": "short label", "insight": "one sentence"}}
  ],
  "market_trends": ["string"],
  "growth_drivers": ["string"],
  "risks": ["string"],
  "recommendations": ["specific actionable next step"],
  "article_insights": [
    {{"index": 0, "classification": "one allowed value", "relevance_score": 0, "why_it_matters": "one sentence tied to the business", "summary": "1-2 sentence neutral summary"}}
  ]
}}
impact_score and relevance_score are integers from 0 to 100. Provide an article_insights entry for every index."""


def coerce_int(value, fallback=0):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (ValueError, TypeError):
        return fallback


def run_analysis(articles, profile, topic, custom_prompt, prior):
    client = get_client()
    if client is None:
        return None, "GROQ_API_KEY is not configured on the server."
    prompt = build_prompt(articles, profile, topic, custom_prompt, prior)
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a rigorous competitive intelligence analyst. You always answer with strict JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.35,
            max_tokens=4096,
        )
        parsed = json.loads(completion.choices[0].message.content)
        if not isinstance(parsed, dict):
            return None, "Model returned an unexpected payload."
        return parsed, None
    except Exception as error:
        return None, str(error)


def merge_enrichment(articles, analysis):
    insights = analysis.get("article_insights", [])
    by_index = {}
    for item in insights:
        if isinstance(item, dict) and "index" in item:
            try:
                by_index[int(item["index"])] = item
            except (ValueError, TypeError):
                continue
    enriched = []
    for idx, article in enumerate(articles):
        insight = by_index.get(idx, insights[idx] if idx < len(insights) and isinstance(insights[idx], dict) else {})
        enriched.append({
            "title": article["title"],
            "url": article["url"],
            "source": article["source"],
            "domain": article["domain"],
            "published": article["published"],
            "image": article["image"],
            "classification": insight.get("classification", "Neutral Signal"),
            "relevance_score": coerce_int(insight.get("relevance_score"), 0),
            "why_it_matters": insight.get("why_it_matters", ""),
            "summary": insight.get("summary") or article["snippet"],
        })
    enriched.sort(key=lambda item: item["relevance_score"], reverse=True)
    return enriched


def normalize_analysis(analysis):
    analysis["impact_score"] = coerce_int(analysis.get("impact_score"), 0)
    for key in ["market_trends", "growth_drivers", "risks", "recommendations"]:
        value = analysis.get(key)
        analysis[key] = [str(v) for v in value if str(v).strip()] if isinstance(value, list) else []
    competitors = analysis.get("competitor_analysis")
    analysis["competitor_analysis"] = competitors if isinstance(competitors, list) else []
    for field in ["headline_summary", "category", "sentiment", "urgency", "evolution_note"]:
        analysis[field] = str(analysis.get(field, "") or "")
    return analysis


def dispatch_alert(topic, analysis, top_articles):
    if not DISCORD_WEBHOOK_URL:
        return
    fields = []
    for article in top_articles[:3]:
        fields.append({
            "name": f"[{article['classification']}] {article['source']}",
            "value": f"[{article['title'][:110]}]({article['url']})",
            "inline": False,
        })
    payload = {
        "username": "Scrapem",
        "embeds": [{
            "title": f"High-impact signal on \"{topic}\"",
            "description": analysis.get("headline_summary", "")[:600],
            "color": 15158332,
            "fields": fields,
            "footer": {"text": f"Impact {analysis['impact_score']}/100 | {analysis.get('urgency', 'High')} urgency"},
        }],
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=8)
    except Exception:
        pass


def execute_run(topic, profile, custom_prompt):
    articles = gather_articles(topic, MAX_ARTICLES)
    if not articles:
        return {"ok": False, "error": "No live signals were found for this topic. Try a broader keyword."}, 200
    history = load_history()
    prior = history_for_topic(history, topic)
    analysis, error = run_analysis(articles, profile, topic, custom_prompt, prior)
    if analysis is None:
        return {"ok": False, "error": error}, 200
    analysis = normalize_analysis(analysis)
    enriched = merge_enrichment(articles, analysis)
    record = {
        "topic": topic,
        "profile": profile,
        "category": analysis["category"],
        "impact_score": analysis["impact_score"],
        "headline_summary": analysis["headline_summary"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_competitors": [c.get("name", "") for c in analysis["competitor_analysis"][:3] if isinstance(c, dict)],
    }
    if analysis["impact_score"] >= ALERT_THRESHOLD:
        dispatch_alert(topic, analysis, enriched)
        record["alerted"] = True
    save_history(record)
    timeline = [record] + prior[:5]
    payload = {
        "ok": True,
        "meta": {
            "topic": topic,
            "profile": profile,
            "generated_at": record["generated_at"],
            "model": GROQ_MODEL,
            "article_count": len(enriched),
            "alerted": analysis["impact_score"] >= ALERT_THRESHOLD and bool(DISCORD_WEBHOOK_URL),
            "alert_threshold": ALERT_THRESHOLD,
        },
        "analysis": analysis,
        "articles": enriched,
        "timeline": timeline,
    }
    return payload, 200


@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze_endpoint():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or TARGET_TOPIC).strip()
    profile = (data.get("profile") or BUSINESS_PROFILE).strip()
    custom_prompt = (data.get("custom_prompt") or "").strip()
    payload, status = execute_run(topic, profile, custom_prompt)
    return jsonify(payload), status


@app.route("/api/history", methods=["GET"])
def history_endpoint():
    return jsonify({"ok": True, "timeline": load_history()[:HISTORY_LIMIT]})


@app.route("/api/cron", methods=["GET", "POST"])
def cron_job():
    auth_header = request.headers.get("Authorization", "")
    if CRON_SECRET and auth_header != f"Bearer {CRON_SECRET}":
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    payload, status = execute_run(TARGET_TOPIC, BUSINESS_PROFILE, "")
    summary = {
        "ok": payload.get("ok", False),
        "topic": TARGET_TOPIC,
        "impact_score": payload.get("analysis", {}).get("impact_score") if payload.get("ok") else None,
        "article_count": payload.get("meta", {}).get("article_count") if payload.get("ok") else 0,
    }
    return jsonify(summary), status


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "model": GROQ_MODEL, "groq_configured": bool(GROQ_API_KEY)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
