#!/usr/bin/env python3
"""
tools/scraper.py
────────────────────────────────────────────────────────────────
SCRAPERRR — Iran/USA/Israel War News Scraper
Layer 3: Deterministic tool. Atomic and independently testable.

SOP Reference: architecture/scraper_sop.md
Output:        .tmp/articles.json
"""

import os
import sys
import json
import time
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
from dotenv import load_dotenv
try:
    from supabase import create_client, Client
    SUPABASE_ENABLED = True
except ImportError:
    SUPABASE_ENABLED = False

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).parent.parent
TMP_DIR   = ROOT_DIR / ".tmp"
OUT_FILE  = TMP_DIR / "articles.json"
LOG_FILE  = TMP_DIR / "scraper.log"

TMP_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────
# Wrap stdout in UTF-8 to prevent cp1252 crash on Windows when logging emoji
_stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(_stream)
    ]
)
log = logging.getLogger("scraper")

# ── RSS Feed Definitions ───────────────────────────────────────
FEEDS = [
    {
        "source":      "Reuters",
        "url":         "https://feeds.reuters.com/Reuters/worldNews",
        "source_logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Reuters_logo.svg/2560px-Reuters_logo.svg.png"
    },
    {
        "source":      "BBC News",
        "url":         "http://feeds.bbci.co.uk/news/world/rss.xml",
        "source_logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/62/BBC_News_2019.svg/2560px-BBC_News_2019.svg.png"
    },
    {
        "source":      "Al Jazeera",
        "url":         "https://www.aljazeera.com/xml/rss/all.xml",
        "source_logo": "https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Al_Jazeera_Media_Network_logo.svg/2560px-Al_Jazeera_Media_Network_logo.svg.png"
    },
    {
        "source":      "AP News",
        "url":         "https://feeds.apnews.com/rss/apf-topnews",
        "source_logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Associated_Press_logo_2012.svg/2560px-Associated_Press_logo_2012.svg.png"
    },
    {
        "source":      "The Guardian",
        "url":         "https://www.theguardian.com/world/iran/rss",
        "source_logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/The_Guardian.svg/2560px-The_Guardian.svg.png"
    },
]

# ── Keyword Filter ─────────────────────────────────────────────
KEYWORDS = [
    "iran", "israel", "usa", "united states", "american",
    "war", "strike", "attack", "missile", "nuclear",
    "military", "idf", "irgc", "conflict", "bomb",
    "tehran", "tel aviv", "pentagon", "netanyahu", "khamenei",
    "hezbollah", "hamas", "uranium", "sanctions", "airstrike",
    "ballistic", "drone", "zarif", "mossad", "iaea"
]

# ── Helpers ────────────────────────────────────────────────────
def make_id(url: str) -> str:
    """SHA-256 hash of URL → stable, unique article ID."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def is_relevant(title: str, description: str) -> bool:
    """Return True if article matches at least one keyword."""
    text = (title + " " + description).lower()
    return any(kw in text for kw in KEYWORDS)


def clean_summary(text: str, max_len: int = 350) -> str:
    """Strip HTML tags and truncate."""
    import re
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.strip()
    return text[:max_len] + "…" if len(text) > max_len else text


def extract_image(entry) -> str | None:
    """Try various Feed fields for a usable image URL."""
    # media:content
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if m.get("type", "").startswith("image"):
                return m.get("url")
    # media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    # enclosure
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href")
    return None


def parse_date(entry) -> str:
    """Parse published date → ISO8601 UTC string."""
    import email.utils
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            t = email.utils.parsedate_to_datetime(raw)
            return t.astimezone(timezone.utc).isoformat()
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat()


def fetch_feed_with_retry(feed_cfg: dict, retries: int = 3, backoff: int = 2) -> list:
    """Fetch one feed and return matching articles. Retry on failure."""
    source  = feed_cfg["source"]
    url     = feed_cfg["url"]
    logo    = feed_cfg["source_logo"]
    articles = []

    for attempt in range(1, retries + 1):
        try:
            log.info(f"[{source}] Fetching (attempt {attempt}/{retries}): {url}")
            # feedparser handles HTTP internally
            feed = feedparser.parse(url)

            if feed.bozo and not feed.entries:
                raise ValueError(f"Malformed feed: {feed.bozo_exception}")

            for entry in feed.entries:
                title       = entry.get("title", "").strip()
                description = entry.get("summary", entry.get("description", ""))
                link        = entry.get("link", "")

                if not link or not title:
                    continue

                if not is_relevant(title, description):
                    continue

                # Detect tags from title/description
                text = (title + " " + description).lower()
                tags = [kw for kw in ["iran", "israel", "usa", "war", "nuclear", "strike", "military"] if kw in text]

                articles.append({
                    "id":          make_id(link),
                    "title":       title,
                    "source":      source,
                    "source_logo": logo,
                    "url":         link,
                    "published":   parse_date(entry),
                    "summary":     clean_summary(description),
                    "image_url":   extract_image(entry),
                    "tags":        tags[:4],
                    "saved":       False,
                    "fetched_at":  datetime.now(timezone.utc).isoformat()
                })

            log.info(f"[{source}] ✅ {len(articles)} relevant articles found")
            return articles

        except Exception as exc:
            log.warning(f"[{source}] ❌ Attempt {attempt} failed: {exc}")
            if attempt < retries:
                log.info(f"[{source}] ⏳ Retrying in {backoff}s…")
                time.sleep(backoff)

    log.error(f"[{source}] 🔴 All {retries} attempts failed — skipping this feed.")
    return []


def load_existing() -> dict:
    """Load existing articles.json or return empty structure."""
    if OUT_FILE.exists():
        try:
            with open(OUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Could not read existing articles: {e}")
    return {"articles": [], "last_fetched": None, "total_count": 0, "sources_hit": []}


def is_cache_fresh(last_fetched: str | None, hours: int = 24) -> bool:
    """Return True if cache is < hours old."""
    if not last_fetched:
        return False
    try:
        last = datetime.fromisoformat(last_fetched)
        return (datetime.now(timezone.utc) - last) < timedelta(hours=hours)
    except Exception:
        return False


def sync_to_supabase(articles: list, casualties: dict):
    """Upsert articles and snapshot casualties to Supabase."""
    if not SUPABASE_ENABLED:
        log.warning("supabase package not installed — skipping sync.")
        return

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        log.warning("SUPABASE_URL / SUPABASE_ANON_KEY not set — skipping sync.")
        return

    try:
        sb: Client = create_client(url, key)
        log.info("☁️ Syncing to Supabase…")

        # Upsert articles (id is PK — safe to re-run)
        rows = [
            {
                "id":          a["id"],
                "title":       a["title"],
                "source":      a["source"],
                "source_logo": a.get("source_logo"),
                "url":         a["url"],
                "published":   a.get("published"),
                "summary":     a.get("summary"),
                "image_url":   a.get("image_url"),
                "tags":        a.get("tags", []),
                "fetched_at":  a.get("fetched_at")
            }
            for a in articles
        ]
        if rows:
            # Upsert in batches of 100 to avoid request limits
            for i in range(0, len(rows), 100):
                sb.table("articles").upsert(rows[i:i+100]).execute()
            log.info(f"☁️  ✅ Upserted {len(rows)} articles")

        # Insert casualty snapshot
        now = datetime.now(timezone.utc).isoformat()
        snap_rows = [
            {"recorded_at": now, "country": country, "dead": vals["dead"], "injured": vals["injured"]}
            for country, vals in casualties.items()
        ]
        if snap_rows:
            sb.table("casualty_snapshots").insert(snap_rows).execute()
            log.info(f"☁️  ✅ Inserted {len(snap_rows)} casualty snapshot rows")

    except Exception as exc:
        log.error(f"☁️ Supabase sync failed: {exc}")


def extract_dynamic_casualties(articles: list) -> dict:
    """Scan article headlines and summaries for death numbers per country."""
    # ── Verified baseline (as of March 5, 2026) ─────────────────────────────
    # Sources: CBS News, Time, CBC, The Guardian, HRANA, Iran Foundation of Martyrs
    # NOTE: All counts are NATIONALS of each country, not foreign troops stationed there.
    # - Qatar: 0 Qatari nationals killed. Deaths reported "in Qatar" were US service members.
    # - Kuwait: Drone struck a US facility in Port Shuaiba; 3 non-US local deaths confirmed.
    # - USA: 6 US service members killed (103rd Sustainment Command, Kuwait base).
    casualties = {
        "Iran":    {"dead": 1230, "injured": 6186},   # Iran Foundation of Martyrs / Health Ministry
        "Israel":  {"dead": 12,   "injured": 336},    # Iranian missile strikes; IDF + civilians
        "USA":     {"dead": 6,    "injured": 18},     # 103rd Sustainment Command (Port Shuaiba, Kuwait)
        "Lebanon": {"dead": 72,   "injured": 200},    # Israeli strikes on Hezbollah/civilian areas
        "Iraq":    {"dead": 12,   "injured": 31},     # PMF strikes + coalition operations
        "UAE":     {"dead": 3,    "injured": 0},      # Iranian missile fragments / debris
        "Kuwait":  {"dead": 3,    "injured": 9},      # Local deaths at Port Shuaiba (excl. US troops)
        "Bahrain": {"dead": 1,    "injured": 4},      # Single reported death
        "Oman":    {"dead": 1,    "injured": 2},      # Single reported death
    }
    
    # Regex pattern: look for (Number) (words/spaces) (killed|dead|deaths|fatalities) (words/spaces) (Country)
    # OR (Country) (words/spaces) (Number) (words/spaces) (killed|dead|deaths|fatalities)
    # This is a broad heuristic capable of catching live reports.
    countries_regex = r"(Iran|Israel|USA|US|United States|Lebanon|Gaza|Iraq|Syria|Yemen|Oman|Bahrain|Kuwait|Qatar|UAE|United Arab Emirates)"
    
    # Pattern 1: e.g., "15 killed in Iran"
    pat1 = re.compile(r"([0-9]+(?:\,[0-9]+)?)\s+(?:people\s+|civilians\s+|soldiers\s+)?(?:killed|dead|died|fatalities|deaths).*?(?:in|near|from)\s+" + countries_regex, re.IGNORECASE)
    # Pattern 2: e.g., "Iran reports 20 dead"
    pat2 = re.compile(countries_regex + r".*?(?:reports|sees|suffers)\s+([0-9]+(?:\,[0-9]+)?)\s+(?:killed|dead|deaths|fatalities)", re.IGNORECASE)

    for article in articles:
        text = (article.get("title", "") + " " + article.get("summary", "")).replace(",", "")
        
        matches1 = pat1.findall(text)
        for num_str, country in matches1:
            try:
                num = int(num_str)
                country = "USA" if country.upper() in ["US", "UNITED STATES"] else country.title()
                country = "UAE" if country.upper() == "UNITED ARAB EMIRATES" else country
                if country not in casualties:
                    casualties[country] = {"dead": 0, "injured": 0}
                if num > casualties[country]["dead"]:
                    casualties[country]["dead"] = num
            except Exception:
                pass
                
        matches2 = pat2.findall(text)
        for country, num_str in matches2:
            try:
                num = int(num_str)
                country = "USA" if country.upper() in ["US", "UNITED STATES"] else country.title()
                country = "UAE" if country.upper() == "UNITED ARAB EMIRATES" else country
                if country not in casualties:
                    casualties[country] = {"dead": 0, "injured": 0}
                if num > casualties[country]["dead"]:
                    casualties[country]["dead"] = num
            except Exception:
                pass
                
    # Formatting for payload
    formatted = {}
    for c, stats in casualties.items():
        formatted[c] = {"dead": str(stats["dead"]), "injured": str(stats["injured"])}
        
    return formatted

# ── Main ───────────────────────────────────────────────────────
def run(force: bool = False) -> dict:
    """
    Main entry point.
    force=True  → bypass 24h gate (used by /api/refresh endpoint)
    force=False → skip if cache is fresh
    """
    existing = load_existing()

    if not force and is_cache_fresh(existing.get("last_fetched")):
        log.info("✅ Cache is fresh (< 24h). Skipping re-fetch.")
        return existing

    log.info("🚀 Starting full scrape run…")
    now_utc   = datetime.now(timezone.utc).isoformat()
    old_ids   = {a["id"] for a in existing.get("articles", [])}
    old_saved = {a["id"]: a.get("saved", False) for a in existing.get("articles", [])}

    new_articles = []
    sources_hit  = []

    for feed_cfg in FEEDS:
        fetched = fetch_feed_with_retry(feed_cfg)
        if fetched:
            sources_hit.append(feed_cfg["source"])

        for article in fetched:
            aid = article["id"]
            if aid in old_ids:
                continue  # deduplicate — skip if already stored
            # Honour any previously saved flag from localStorage sync (best effort)
            article["saved"] = old_saved.get(aid, False)
            new_articles.append(article)

    log.info(f"📰 {len(new_articles)} new articles scraped across {len(sources_hit)} sources")

    # Merge: new articles on top, preserve old
    merged = new_articles + existing.get("articles", [])

    # Sort by published (newest first)
    try:
        merged.sort(key=lambda a: a.get("published", ""), reverse=True)
    except Exception:
        pass

    dynamic_casualties = extract_dynamic_casualties(merged)

    payload = {
        "articles":     merged,
        "last_fetched": now_utc,
        "total_count":  len(merged),
        "sources_hit":  list(set(sources_hit)),
        "casualties":   dynamic_casualties
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    log.info(f"💾 Saved {len(merged)} total articles → {OUT_FILE}")

    # Phase 2 — sync to Supabase
    sync_to_supabase(merged, dynamic_casualties)

    return payload


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    result = run(force=force)
    print(f"\n✅ Done — {result['total_count']} articles | Sources: {result['sources_hit']}")
