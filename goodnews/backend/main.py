"""
main.py — Good News Only: FastAPI Backend
==========================================

Architecture overview:
  1. Fetch articles from free RSS feeds (no API key needed)
  2. Run each headline + summary through a pretrained sentiment model
  3. Keep only articles that score as POSITIVE above a threshold
  4. Serve them through a single /api/news endpoint
  5. Cache results for 15 minutes so we don't hammer the feeds

Sentiment model used: cardiffnlp/twitter-roberta-base-sentiment-latest
  - Pretrained on ~58M tweets, very good at tone detection
  - Three labels: positive / neutral / negative
  - Runs fully locally via HuggingFace transformers
  - Loads once at startup (~500MB, cached after first download)

No paid services. No API keys. Runs 100% locally.
"""

import requests
import time
import logging
import asyncio
import hashlib
from datetime import datetime
from typing import Optional

import feedparser
import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from transformers import pipeline

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Good News Only API",
    description="Returns only positive and uplifting news articles.",
    version="1.0.0",
)

# Allow the frontend (any origin in dev) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten this in production
    allow_methods=["GET"],
    allow_headers=["*"],
)

sentiment_pipeline = pipeline(
    task="sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest",
    # Use top_k=None to get scores for all three labels (pos/neu/neg)
    top_k=None,
    truncation=True,
    max_length=128,        # enough for a headline + summary
)


# ─── RSS Feed Sources ─────────────────────────────────────────────────────────
# These are free, no-key RSS feeds that tend to have uplifting content.
# We cast a wide net and let sentiment filtering do the real work.

RSS_FEEDS = [
    # Dedicated good news sources
    {"url": "https://www.goodnewsnetwork.org/feed/",        "source": "Good News Network"},
    {"url": "https://www.positive.news/feed/",              "source": "Positive News"},
    {"url": "https://feeds.npr.org/1001/rss.xml",           "source": "NPR News"},

    # Science & tech often has uplifting breakthroughs
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "source": "BBC Science"},
    {"url": "https://rss.sciencedaily.com/top/science.xml", "source": "Science Daily"},

    # Health & wellness
    {"url": "https://feeds.bbci.co.uk/news/health/rss.xml", "source": "BBC Health"},

    # Tech innovation
    {"url": "https://techcrunch.com/feed/",                 "source": "TechCrunch"},

    # World good news
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",  "source": "BBC World"},
]

# ─── Config ───────────────────────────────────────────────────────────────────

# Minimum positive sentiment score to include an article (0.0 – 1.0)
# 0.55 is a good balance: catches most uplifting content, filters most negativity
POSITIVE_THRESHOLD = 0.55

# How long to cache results (seconds). Avoids re-fetching on every page load.
CACHE_TTL_SECONDS = 15 * 60   # 15 minutes

# Max articles to return per request
MAX_ARTICLES = 30

# ─── Simple In-Memory Cache ───────────────────────────────────────────────────

_cache: dict = {}   # key → {"data": [...], "expires": float}

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and entry["expires"] > time.time():
        return entry["data"]
    return None

def cache_set(key: str, data, ttl: int = CACHE_TTL_SECONDS):
    _cache[key] = {"data": data, "expires": time.time() + ttl}

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
    category: Optional[str] = None

# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_id(url: str) -> str:
    """Stable short ID from the article URL."""
    return hashlib.md5(url.encode()).hexdigest()[:10]

def clean_text(text: str) -> str:
    """Strip HTML tags and extra whitespace for cleaner sentiment analysis."""
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&\w+;", " ", text)   # HTML entities
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_image(entry) -> Optional[str]:
    """Try to extract a thumbnail image URL from a feed entry."""
    # Method 1: media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")

    # Method 2: media:content
    if hasattr(entry, "media_content") and entry.media_content:
        for media in entry.media_content:
            if media.get("type", "").startswith("image"):
                return media.get("url")

    # Method 3: enclosures (podcast/image feeds)
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href") or enc.get("url")

    return None



from gradio_client import Client

client = Client("dhanashree2311/news-sentiment-app")

def analyze_sentiment(text: str) -> float:
    try:
        result = client.predict(
            text[:512],
            api_name="/predict"
        )

        if "Positive" in result:
            confidence = float(
                result.split("Confidence:")[1]
                .replace(")", "")
                .strip()
            )
            return confidence

        return 0.0

    except Exception as e:
        log.warning(f"Space error: {e}")
        return 0.0



async def fetch_feed(feed_info: dict) -> list[dict]:
    """
    Fetch and parse one RSS feed asynchronously.
    Returns a list of raw article dicts.
    """
    url    = feed_info["url"]
    source = feed_info["source"]

    try:
        # feedparser is sync; run it in a thread executor to stay async
        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(None, feedparser.parse, url)

        articles = []
        for entry in parsed.entries[:15]:   # cap per feed to avoid overload
            title   = clean_text(getattr(entry, "title",   "") or "")
            summary = clean_text(getattr(entry, "summary", "") or
                                 getattr(entry, "description", "") or "")
            link    = getattr(entry, "link", "") or ""

            if not title or not link:
                continue

            # Published date — handle various formats
            published = None
            if hasattr(entry, "published"):
                published = entry.published
            elif hasattr(entry, "updated"):
                published = entry.updated

            articles.append({
                "title":     title,
                "summary":   summary[:400],   # cap summary length
                "url":       link,
                "source":    source,
                "published": published,
                "image_url": extract_image(entry),
            })

        log.info(f"Fetched {len(articles)} articles from {source}")
        return articles

    except Exception as e:
        log.error(f"Failed to fetch {source}: {e}")
        return []

async def fetch_all_feeds() -> list[dict]:
    """Fetch all RSS feeds concurrently."""
    tasks = [fetch_feed(feed) for feed in RSS_FEEDS]
    results = await asyncio.gather(*tasks)
    # Flatten list of lists
    all_articles = [article for feed_articles in results for article in feed_articles]
    log.info(f"Total articles fetched: {len(all_articles)}")
    return all_articles

def filter_positive(articles: list[dict], threshold: float = POSITIVE_THRESHOLD) -> list[Article]:
    """
    Run sentiment analysis on each article and keep only positive ones.

    We analyze: title + first 200 chars of summary
    Rationale: The headline captures tone most clearly. Summary adds context.
    """
    positive_articles = []

    for raw in articles:
        # Build the text to analyze
        analysis_text = raw["title"]
        if raw["summary"]:
            analysis_text += " " + raw["summary"][:200]

        

        score = analyze_sentiment(analysis_text)

        log.debug(f"[{score:.2f}] {raw['title'][:60]}")

        if score >= threshold:
            positive_articles.append(
                Article(
                    id             = make_id(raw["url"]),
                    title          = raw["title"],
                    summary        = raw["summary"],
                    url            = raw["url"],
                    source         = raw["source"],
                    published      = raw["published"],
                    positive_score = score,
                    image_url      = raw.get("image_url"),
                )
            )

    # Sort by most positive first
    positive_articles.sort(key=lambda a: a.positive_score, reverse=True)

    log.info(f"Kept {len(positive_articles)} positive articles out of {len(articles)}")
    return positive_articles

# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "Good News Only API is running 🌟"}

@app.get("/api/news", response_model=list[Article])
async def get_news(
    limit:     int   = Query(default=20,   ge=1,   le=MAX_ARTICLES, description="Max articles to return"),
    threshold: float = Query(default=0.55, ge=0.0, le=1.0,          description="Minimum positive score"),
    refresh:   bool  = Query(default=False,                          description="Bypass cache and re-fetch"),
):
    """
    Returns a list of positive news articles, filtered by sentiment.

    - Results are cached for 15 minutes
    - Set ?refresh=true to force a fresh fetch
    - Adjust ?threshold=0.7 for stricter positivity filtering
    """
    cache_key = f"news_{threshold}"

    # Return cached data if available and not forcing refresh
    if not refresh:
        cached = cache_get(cache_key)
        if cached:
            log.info(f"Returning {min(limit, len(cached))} cached articles")
            return cached[:limit]

    # Fetch fresh data
    log.info("Fetching fresh news from RSS feeds…")
    raw_articles = await fetch_all_feeds()

    if not raw_articles:
        return JSONResponse(
            status_code=503,
            content={"error": "Could not fetch any news feeds. Check your internet connection."}
        )

    # Filter for positivity
    positive = filter_positive(raw_articles, threshold=threshold)

    # Cache the full result set
    cache_set(cache_key, [a.model_dump() for a in positive])

    return positive[:limit]


@app.get("/api/stats")
async def get_stats():
    """Returns info about the last fetch: total fetched, how many passed the filter."""
    # Quick fetch without caching for stats
    raw = await fetch_all_feeds()
    positive = filter_positive(raw)

    return {
        "total_fetched":    len(raw),
        "total_positive":   len(positive),
        "filter_rate":      f"{len(positive)/max(len(raw),1)*100:.1f}%",
        "sources":          len(RSS_FEEDS),
        "threshold":        POSITIVE_THRESHOLD,
        "cached_until":     "15 minutes after last fetch",
    }


@app.get("/api/health")
def health():
    return {
        "status":  "healthy",
        "model": "dhanashree2311/news-distilroberta-sentiment (via HF Space)",
        "sources": len(RSS_FEEDS),
        "cache_ttl_minutes": CACHE_TTL_SECONDS // 60,
    }
