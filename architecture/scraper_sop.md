# SOP: RSS News Scraper — Iran/USA/Israel War Coverage

> **Layer 1 — Architecture Document**
> Do not modify `tools/scraper.py` without first updating this SOP.

---

## 1. Goal
Fetch, filter, de-duplicate, and persist news articles about the Iran/USA/Israel conflict from 5 credible RSS sources. Output a single JSON payload to `.tmp/articles.json`.

---

## 2. RSS Sources
| Source | Feed URL | Notes |
|--------|----------|-------|
| Reuters | `https://feeds.reuters.com/Reuters/worldNews` | General world news — filter required |
| BBC World | `http://feeds.bbci.co.uk/news/world/rss.xml` | General — filter required |
| Al Jazeera | `https://www.aljazeera.com/xml/rss/all.xml` | Broad ME coverage |
| AP News | `https://feeds.apnews.com/rss/apf-topnews` | Top global news |
| The Guardian | `https://www.theguardian.com/world/iran/rss` | Iran-specific feed |

---

## 3. Keyword Filter
An article is included **only if** its `title` or `description` contains **at least one** of:
```
iran, israel, usa, united states, american, war, strike, attack, missile, nuclear,
military, idf, irgc, conflict, bomb, tehran, tel aviv, pentagon, netanyahu, khamenei
```
Match is **case-insensitive**.

---

## 4. De-duplication
- Each article ID = `SHA-256(article.url)`
- Before writing to `.tmp/articles.json`, compare against existing IDs
- If ID already exists → **skip** (do not overwrite, preserve `saved` flag)
- New articles are **prepended** (newest first)

---

## 5. Retry Logic
- On feed fetch failure: retry **3 times** with **5-second backoff**
- After 3 failures: log to `.tmp/scraper.log` and continue with other feeds
- A partial result (some feeds failed) is still valid — log which feeds were hit

---

## 6. Output File
**Path:** `.tmp/articles.json`
**Schema:** See `gemini.md § 2.3`
```json
{
  "articles": [...],
  "last_fetched": "2026-03-05T09:00:00Z",
  "total_count": 42,
  "sources_hit": ["Reuters", "BBC"],
  "casualties": {"..."}
}
```

---

## 7. 24-Hour Refresh Gate
- On startup, read `last_fetched` from existing `.tmp/articles.json`
- If `now - last_fetched < 24 hours` → **skip fetch**, return cached data
- Manual `/api/refresh` endpoint **bypasses** the time gate

---

## 8. Error Codes & Resolution
| Error | Cause | Resolution |
|-------|-------|------------|
| `ConnectionError` | Feed URL unreachable | Retry 3x, then skip |
| `xml.etree.ElementTree.ParseError` | Malformed RSS | Skip feed, log |
| `UnicodeDecodeError` | Encoding issue | Force UTF-8 decode with `errors='replace'` |
| `FileNotFoundError` on `.tmp/` | Directory missing | Auto-create on startup |

---

## 9. Maintenance
- If a feed URL changes → update this SOP **first**, then update `tools/scraper.py`
- If a new source is added → add row to table above, add to `FEEDS` list in script
