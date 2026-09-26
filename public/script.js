function $(id) {
    return document.getElementById(id);
}

function escapeHtml(value) {
    return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function scoreColor(score) {
    if (score >= 75) return "#f0837a";
    if (score >= 50) return "#d9b463";
    return "#6fb58c";
}

function formatDate(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "";
    return parsed.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

/* ---------------------------------------------------------------
   icons for the three-column feature row
   --------------------------------------------------------------- */

const ICONS = {
    radar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M19.8 8.4A9 9 0 1 0 15.6 19.8"/><path d="M16.2 11.4A5 5 0 1 0 13.2 16.5"/><path d="M12 12l7-7"/></svg>',
    bolt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z"/></svg>',
    target: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><circle cx="11" cy="11" r="2.5"/><path d="m16.5 16.5 4 4"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/></svg>',
};

const SEP = ' <span class="sep">·</span> ';

function featureColumn(title, iconKey, parts) {
    if (!parts || !parts.length) return "";
    return `
        <div class="feature">
            <span class="feature-icon">${ICONS[iconKey]}</span>
            <h3>${escapeHtml(title)}</h3>
            <p>${parts.join(SEP)}</p>
        </div>`;
}

function listColumn(title, iconKey, items) {
    if (!items || !items.length) return "";
    return featureColumn(title, iconKey, items.map((item) => escapeHtml(item)));
}

function competitorColumn(competitors) {
    if (!competitors || !competitors.length) return "";
    const parts = competitors.map((comp) => {
        const level = escapeHtml(comp.threat_level || "Low");
        const name = escapeHtml(comp.name || "Unknown");
        return `${level} — ${name}`;
    });
    return featureColumn("Competitor Threat Radar", "radar", parts);
}

function renderPanels(analysis) {
    const columns = [
        competitorColumn(analysis.competitor_analysis),
        listColumn("Market Trends", "bolt", analysis.market_trends),
        listColumn("Growth Drivers", "target", analysis.growth_drivers),
        listColumn("Risks & Threats", "alert", analysis.risks),
        listColumn("Recommended Moves", "check", analysis.recommendations),
    ].filter(Boolean);
    $("panel-grid").innerHTML = columns.join("");
}

/* ---------------------------------------------------------------
   status / loading
   --------------------------------------------------------------- */

function setStatus(state, text) {
    const pill = $("agent-status");
    pill.classList.remove("working", "error");
    if (state) pill.classList.add(state);
    $("status-text").textContent = text;
}

function toggleLoading(isLoading) {
    const button = $("run-btn");
    button.classList.toggle("loading", isLoading);
    button.disabled = isLoading;
    $("skeleton").hidden = !isLoading;
    if (isLoading) {
        $("results").hidden = true;
        $("feedback").hidden = true;
    }
}

function showError(message) {
    const box = $("feedback");
    box.hidden = false;
    box.className = "feedback error";
    box.textContent = message;
    setStatus("error", "Sweep failed");
}

/* ---------------------------------------------------------------
   briefing
   --------------------------------------------------------------- */

function countUp(score) {
    const counter = $("impact-score");
    counter.style.color = scoreColor(score);
    const start = performance.now();
    const duration = 700;
    function tick(now) {
        const progress = Math.min(1, (now - start) / duration);
        counter.textContent = String(Math.round(progress * score));
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

function renderBriefing(analysis, meta) {
    countUp(analysis.impact_score || 0);

    const urgency = (analysis.urgency || "Medium").toLowerCase();
    const tags = [];
    if (analysis.category) {
        tags.push(`<span class="tag">${escapeHtml(analysis.category)}</span>`);
    }
    tags.push(`<span class="tag tag-urgency-${urgency}">${escapeHtml(analysis.urgency || "Medium")} urgency</span>`);
    if (analysis.sentiment) {
        tags.push(`<span class="tag">${escapeHtml(analysis.sentiment)} sentiment</span>`);
    }
    $("briefing-tags").innerHTML = tags.join("");

    $("headline-summary").textContent = analysis.headline_summary || "No summary was produced for this sweep.";

    const evolution = $("evolution-note");
    if (analysis.evolution_note) {
        evolution.hidden = false;
        evolution.textContent = analysis.evolution_note;
    } else {
        evolution.hidden = true;
    }

    const alerted = meta.alerted ? "Alert dispatched" : "Below alert threshold";
    $("briefing-meta").innerHTML = [
        `<span><strong>Topic:</strong> ${escapeHtml(meta.topic)}</span>`,
        `<span><strong>Signals:</strong> ${meta.article_count}</span>`,
        `<span><strong>Model:</strong> ${escapeHtml(meta.model)}</span>`,
        `<span><strong>Dispatch:</strong> ${alerted} (${meta.alert_threshold}+)</span>`,
        `<span><strong>Run:</strong> ${escapeHtml(formatDate(meta.generated_at))}</span>`,
    ].join("");
}

/* ---------------------------------------------------------------
   signal cards
   --------------------------------------------------------------- */

function buildCard(article) {
    const card = document.createElement("article");
    card.className = "card";

    const dateText = formatDate(article.published);
    const meta = [article.source, dateText].filter(Boolean).map(escapeHtml).join(" · ");

    card.innerHTML = `
        <span class="classification">${escapeHtml(article.classification)}</span>
        <h3 class="card-title">
            <a href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(article.title)}</a>
        </h3>
        <p class="card-meta">${meta}</p>
        <p class="card-summary">${escapeHtml(article.summary)}</p>
        ${article.why_it_matters
            ? `<p class="why"><span>Why it matters:</span>${escapeHtml(article.why_it_matters)}</p>`
            : ""}
    `;
    return card;
}

function renderArticles(articles) {
    const grid = $("article-grid");
    grid.innerHTML = "";
    articles.forEach((article) => grid.appendChild(buildCard(article)));
    $("feed-count").textContent = `${articles.length} classified signals`;
}

function renderTimeline(timeline) {
    const list = $("timeline");
    if (!timeline || !timeline.length) {
        list.innerHTML = `<li><span class="timeline-empty">No prior runs recorded yet. Each sweep is stored so the agent can track how the landscape evolves.</span></li>`;
        return;
    }
    list.innerHTML = timeline.map((item) => {
        const score = item.impact_score || 0;
        return `
            <li>
                <span class="timeline-score" style="color:${scoreColor(score)}">${score}</span>
                <div class="timeline-main">
                    <strong>${escapeHtml(item.category || "Signal")}</strong>
                    <p>${escapeHtml(item.headline_summary || "")}</p>
                </div>
                <span class="timeline-time">${escapeHtml(formatDate(item.generated_at))}</span>
            </li>`;
    }).join("");
}

/* ---------------------------------------------------------------
   run loop
   --------------------------------------------------------------- */

async function runDiscovery(event) {
    if (event) event.preventDefault();
    const topic = $("topic").value.trim();
    const profile = $("profile").value.trim();
    const customPrompt = $("custom-prompt").value.trim();

    toggleLoading(true);
    setStatus("working", "Perceiving live signals…");
    $("skeleton").scrollIntoView({ behavior: "smooth", block: "start" });

    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ topic, profile, custom_prompt: customPrompt }),
        });
        const data = await response.json();

        if (!data.ok) {
            toggleLoading(false);
            showError(data.error || "The agent could not complete this sweep.");
            return;
        }

        toggleLoading(false);
        $("results").hidden = false;
        renderBriefing(data.analysis, data.meta);
        renderPanels(data.analysis);
        renderArticles(data.articles);
        renderTimeline(data.timeline);
        setStatus(null, "Sweep complete");
        $("results").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        toggleLoading(false);
        showError(`Network error: ${error.message}`);
    }
}

function init() {
    $("discovery-form").addEventListener("submit", runDiscovery);
    document.querySelectorAll(".chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            $("topic").value = chip.dataset.topic;
            runDiscovery();
        });
    });
}

document.addEventListener("DOMContentLoaded", init);
