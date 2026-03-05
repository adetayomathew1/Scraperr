# gemini.md — Project Constitution

> **Law File.** This document is the single source of truth for all schemas, rules, and architecture.
> Only update when: a schema changes, a rule is added, or architecture is modified.
> `gemini.md` is *law*. Planning files are *memory*.

---

## 1. Project Identity
- **Project Name:** SCRAPERRR — Iran/USA/Israel War Intelligence Dashboard
- **North Star:** Collect, display, and let users save the latest war news articles from credible sources — refreshed every 24 hrs — in a stunning interactive dashboard.
- **Owner:** System Pilot + User

---

## 2. Data Schema (Input / Output)

> ✅ **SCHEMA CONFIRMED — CODING IS UNBLOCKED.**

### 2.1 Input Schema (Raw RSS / Scrape Feed)
```json
{
  "feed_url": "https://example.com/rss",
  "source_name": "Reuters",
  "source_logo": "https://...",
  "filter_keywords": ["iran", "israel", "usa", "war", "strike", "nuclear", "attack", "military"]
}
```

### 2.2 Processed Article Schema (Stored in `.tmp/articles.json`)
```json
{
  "id": "sha256-hash-of-url",
  "title": "string",
  "source": "Reuters | BBC | Al Jazeera | AP | The Guardian",
  "source_logo": "url | null",
  "url": "https://...",
  "published": "2026-03-05T09:00:00Z",
  "summary": "string (first 300 chars of description)",
  "image_url": "string | null",
  "tags": ["iran", "strike"],
  "saved": false,
  "fetched_at": "2026-03-05T09:00:00Z"
}
```

### 2.3 Output / Payload Schema (Served to Dashboard)
```json
{
  "articles": [ "...Article objects..." ],
  "last_fetched": "2026-03-05T09:00:00Z",
  "total_count": 42,
  "sources_hit": ["Reuters", "BBC", "Al Jazeera"],
  "casualties": {
    "Region": { "dead": "string", "injured": "string" }
  }
}
```

### 2.4 Saved Articles Schema (Persisted in localStorage)
```json
{
  "saved_ids": ["sha256-id-1", "sha256-id-2"],
  "saved_at": { "sha256-id-1": "2026-03-05T10:00:00Z" }
}
```

---

## 3. Integrations & Services
| Service | Status | Notes |
|---------|--------|-------|
| Reuters RSS | ✅ Active | `https://feeds.reuters.com/Reuters/worldNews` |
| BBC World RSS | ✅ Active | `http://feeds.bbci.co.uk/news/world/rss.xml` |
| Al Jazeera RSS | ✅ Active | `https://www.aljazeera.com/xml/rss/all.xml` |
| AP News RSS | ✅ Active | `https://rss.ap.org/...` |
| The Guardian RSS | ✅ Active | `https://www.theguardian.com/world/iran/rss` |
| Supabase | ⏳ Pending | Phase 2 — DB integration later |
| Local HTTP Server | ✅ Active | Flask dev server on port 5000 |

---

## 4. Behavioral Rules
- **Refresh Cycle:** Fetch new articles every 24 hours. If no new articles → do nothing.
- **De-duplication:** Never store the same article URL twice. Use SHA-256 hash of URL as ID.
- **Keyword Filter:** Only include articles matching at least one keyword from the filter list.
- **Saved Articles:** Persist in `localStorage`. Survive page refresh. Never auto-delete saved items.
- **No PII Storage:** Do not store any user-identifying information.
- **Retry Logic:** If a feed fails, retry up to 3 times with 5-second backoff. Log failures.
- **Date Range:** Prioritize articles from the start of the conflict onwards.
- **Do Not:** Hardcode any API key or secret in a Python script. Use `.env`.

---

## 5. Architectural Invariants (A.N.T. 3-Layer)
- **Layer 1 — Architecture (`architecture/`)**: SOPs in Markdown. Logic changes → update SOP *first*.
- **Layer 2 — Navigation**: This agent routes data between Scraper → Server → Dashboard.
- **Layer 3 — Tools (`tools/`)**: Deterministic Python scripts. Atomic and independently testable.
- **`.tmp/`**: All scraped JSON, logs, intermediates. Never committed to cloud payload.
- **`.env`**: API keys and secrets. Never hardcoded.

---

## 6. Maintenance Log
| Date | Change | Phase |
|------|--------|-------|
| 2026-03-05 | Initial constitution created | Blueprint |
| 2026-03-05 | Schema confirmed — Iran/USA/Israel War Dashboard | Blueprint ✅ |
| 2026-03-05 | Fixed casualty tracker | Execution |
