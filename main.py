"""
main.py — Good News Only: FastAPI Backend (OPTIMIZED v3)
=========================================================

Key performance improvements:
  1. VADER sentiment — ultra-lightweight, ~2MB, no model download, <1s for 100 articles
  2. Background scheduler fetches & analyzes every 20 mins — users never wait
  3. Feeds fetched in parallel (ThreadPoolExecutor)
  4. Only NEW articles are analyzed (incremental fetch via seen URLs set)
  5. /api/news reads from pre-built store → responds in <50ms
  6. App starts immediately; background job runs once at startup silently

No transformers. No Gradio. No API keys. Runs 100% locally.
"""

import feedparser
import time
import logging
import hashlib
import re
import threading
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    force=True
)
log = logging.getLogger(__name__)

# ─── VADER — loads instantly, ~2MB, no GPU needed ────────────────────────────
vader = SentimentIntensityAnalyzer()
log.info("✅ VADER sentiment analyzer loaded")

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Good News Only API",
    description="Returns only positive and uplifting news articles.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ─── RSS Feed Sources ─────────────────────────────────────────────────────────
RSS_FEEDS = [
    {"url": "https://www.goodnewsnetwork.org/feed/",        "source": "Good News Network"},
    {"url": "https://www.positive.news/feed/",              "source": "Positive News"},
    {"url": "https://feeds.npr.org/1001/rss.xml",           "source": "NPR News"},
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "source": "BBC Science"},
    {"url": "https://rss.sciencedaily.com/top/science.xml", "source": "Science Daily"},
    {"url": "https://feeds.bbci.co.uk/news/health/rss.xml", "source": "BBC Health"},
    {"url": "https://techcrunch.com/feed/",                 "source": "TechCrunch"},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",  "source": "BBC World"},
]

# ─── Config ───────────────────────────────────────────────────────────────────
POSITIVE_THRESHOLD = 0.55      # 0.0–1.0 (VADER compound -1→+1 normalized to 0→1)
MAX_ARTICLES       = 30
REFRESH_INTERVAL   = 20        # minutes between background fetches
MAX_PARALLEL_FEEDS = 8         # fetch all feeds simultaneously

# ─── Global Store ─────────────────────────────────────────────────────────────
_article_store: list[dict] = []
_store_built_at: Optional[float] = None
_seen_urls: set[str] = set()

# ─── Data Models ──────────────────────────────────────────────────────────────
class Article(BaseModel):
    id: str
    title: str
    summary: str
    url: str
    source: str
    published: Optional[str]
    positive_score: float
    image_url: Optional[str] = None

# ─── Helpers ──────────────────────────────────────────────────────────────────
def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:10]

def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&\w+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_image(entry) -> Optional[str]:
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    if hasattr(entry, "media_content") and entry.media_content:
        for media in entry.media_content:
            if media.get("type", "").startswith("image"):
                return media.get("url")
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href") or enc.get("url")
    return None

# ─── Sentiment (VADER — instant, no network, no GPU) ─────────────────────────
def analyze_sentiment(text: str) -> float:
    """
    VADER runs locally in microseconds.
    compound: -1 (most negative) → +1 (most positive)
    normalized to 0→1 to match threshold logic.
    """
    scores = vader.polarity_scores(text[:512])
    return (scores["compound"] + 1) / 2

# ─── Feed Fetching ────────────────────────────────────────────────────────────
def fetch_feed_sync(feed_info: dict) -> list[dict]:
    url, source = feed_info["url"], feed_info["source"]
    try:
        parsed = feedparser.parse(url)
        articles = []
        for entry in parsed.entries[:15]:
            title   = clean_text(getattr(entry, "title", "") or "")
            summary = clean_text(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
            link    = getattr(entry, "link", "") or ""
            if not title or not link:
                continue
            articles.append({
                "title":     title,
                "summary":   summary[:400],
                "url":       link,
                "source":    source,
                "published": getattr(entry, "published", None) or getattr(entry, "updated", None),
                "image_url": extract_image(entry),
            })
        log.info(f"Fetched {len(articles)} articles from {source}")
        return articles
    except Exception as e:
        log.error(f"Failed to fetch {source}: {e}")
        return []

# ─── Background Job ───────────────────────────────────────────────────────────
def background_refresh():
    """
    Runs every REFRESH_INTERVAL minutes.
    Fetches all feeds → skips seen URLs → runs VADER (instant) → updates store.
    Users are NEVER blocked by this.
    """
    global _article_store, _store_built_at, _seen_urls

    try:
        log.info("🔄 Background job started...")
        start = time.time()

        # 1. Fetch all feeds in parallel
        all_raw = []
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_FEEDS) as executor:
            futures = [executor.submit(fetch_feed_sync, feed) for feed in RSS_FEEDS]
            for f in as_completed(futures):
                all_raw.extend(f.result())

        log.info(f"Total fetched: {len(all_raw)} articles")

        # 2. Only process NEW articles (incremental)
        new_articles = [a for a in all_raw if a["url"] not in _seen_urls]
        log.info(f"New articles: {len(new_articles)} | Already seen: {len(all_raw) - len(new_articles)}")

        if not new_articles:
            log.info("No new articles. Store unchanged.")
            return

        # 3. VADER sentiment — runs locally, <1 second for all articles
        new_positive = []
        for article in new_articles:
            text  = article["title"] + " " + article["summary"][:200]
            score = analyze_sentiment(text)
            _seen_urls.add(article["url"])

            if score >= POSITIVE_THRESHOLD:
                new_positive.append({
                    "id":             make_id(article["url"]),
                    "title":          article["title"],
                    "summary":        article["summary"],
                    "url":            article["url"],
                    "source":         article["source"],
                    "published":      article["published"],
                    "positive_score": round(score, 3),
                    "image_url":      article.get("image_url"),
                })

        # 4. Merge, sort by score, cap at 100
        combined = _article_store + new_positive
        combined.sort(key=lambda a: a["positive_score"], reverse=True)
        _article_store  = combined[:100]
        _store_built_at = time.time()

        elapsed = time.time() - start
        log.info(f"✅ Done in {elapsed:.1f}s | {len(new_positive)} new positive | store total: {len(_article_store)}")

    except Exception as e:
        log.error(f"❌ Background job crashed: {e}", exc_info=True)

# ─── Scheduler ────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.add_job(background_refresh, "interval", minutes=REFRESH_INTERVAL, id="news_refresh")
scheduler.start()

# Run once immediately at startup (in background thread so app starts instantly)
threading.Thread(target=background_refresh, daemon=True).start()
log.info(f"🚀 App ready. Background job runs every {REFRESH_INTERVAL} mins.")

# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "Good News Only API is running 🌟"}


@app.get("/api/news", response_model=list[Article])
def get_news(
    limit:     int   = Query(default=20,   ge=1,   le=MAX_ARTICLES),
    threshold: float = Query(default=0.55, ge=0.0, le=1.0),
    refresh:   bool  = Query(default=False),
):
    """
    ⚡ Returns pre-analyzed positive articles from the in-memory store.
    Responds in <50ms. Background job keeps the store fresh every 20 mins.
    """
    if refresh:
        threading.Thread(target=background_refresh, daemon=True).start()
        log.info("Manual refresh triggered via ?refresh=true")

    if not _article_store:
        return JSONResponse(
            status_code=503,
            content={"error": "News is still loading. Please try again in 10 seconds."}
        )

    filtered = [a for a in _article_store if a["positive_score"] >= threshold]
    return filtered[:limit]


@app.get("/api/status")
def get_status():
    """Check this to confirm the background job is working."""
    last_updated = None
    if _store_built_at:
        secs_ago     = int(time.time() - _store_built_at)
        last_updated = f"{secs_ago // 60}m {secs_ago % 60}s ago"

    next_run = scheduler.get_job("news_refresh").next_run_time
    return {
        "articles_in_store":     len(_article_store),
        "seen_urls_total":       len(_seen_urls),
        "last_updated":          last_updated or "not yet — still loading",
        "next_refresh":          str(next_run),
        "refresh_interval_mins": REFRESH_INTERVAL,
        "threshold":             POSITIVE_THRESHOLD,
        "sentiment_engine":      "VADER (local, no API, no GPU)",
    }


@app.get("/api/health")
def health():
    return {
        "status":                "healthy",
        "sentiment_engine":      "VADER (vaderSentiment)",
        "memory_usage":          "~2MB (vs ~500MB for transformers)",
        "sources":               len(RSS_FEEDS),
        "refresh_interval_mins": REFRESH_INTERVAL,
    }
