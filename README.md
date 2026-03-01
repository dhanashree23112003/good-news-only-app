# ☀️ Good News Only
### *Because the world isn't as bad as your news feed makes it look.*

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-⚡_Blazing_Fast-009688?style=for-the-badge&logo=fastapi)
![VADER](https://img.shields.io/badge/Sentiment-VADER-yellow?style=for-the-badge)
![HuggingFace](https://img.shields.io/badge/Deployed_on-HuggingFace_🤗-orange?style=for-the-badge)
![Vibes](https://img.shields.io/badge/Vibes-Immaculate-ff69b4?style=for-the-badge)

**A news app that ruthlessly filters out everything depressing.**
**No doom. No gloom. Just pure, unapologetic good vibes.**

[🌐 Live App](https://dhanashree2311-news-sentiment-app.hf.space/api/news) • [📊 Status](https://dhanashree2311-news-sentiment-app.hf.space/api/status) • [📖 Docs](https://dhanashree2311-news-sentiment-app.hf.space/docs)

</div>

---

## 🤯 What Even Is This?

You know how every time you open the news you immediately want to move to a cabin in the woods with no WiFi?

Yeah. This fixes that.

**Good News Only** fetches from 8 RSS feeds, runs every single headline through AI sentiment analysis, and **throws away anything that isn't positive.** What's left? Whale love stories. Cancer breakthroughs. Farmers growing hope in Kenya. The good stuff.

And it does all of this **before you even open the app.** By the time your phone loads, 52 articles are already waiting for you. No spinner. No waiting. Just good news, instantly.

---

## ⚡ The Speed Glow-Up

This app went through a complete transformation. Here's the before and after:

```
BEFORE (v1) — The Dark Ages 🐌
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You open the app
↓ wait...
Fetch 8 RSS feeds (sequential, one by one)     ~5 seconds
↓ wait...
Call Gradio HF Space API (120 times, one by one) ~120 seconds
↓ wait...
Filter results                                   ~1 second
↓
Show articles                              TOTAL: 2+ MINUTES 💀

AFTER (v3) — The Redemption Arc 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Background job runs silently every 20 mins]
  Fetch 8 feeds in parallel                    ~0.8 seconds
  VADER sentiment on 110 articles              ~0.3 seconds
  Store 52 positive articles in memory         instant

You open the app
↓
Read from pre-built store                  TOTAL: <50ms 🔥
```

**That's a 2400x speedup.** Not a typo.

---

## 🧠 How The Sentiment Filter Works

Meet **VADER** — the tiny but mighty brain behind the filtering.

```python
# This is literally all it takes
scores = vader.polarity_scores("Baby pandas discovered in forest 🐼")
# → {'neg': 0.0, 'neu': 0.3, 'pos': 0.7, 'compound': 0.85}

score = (compound + 1) / 2   # normalize to 0→1
# → 0.925  ✅ PASS — you're seeing this article
```

VADER reads every headline + summary and gives it a score from 0.0 (pure doom) to 1.0 (pure sunshine). Anything above **0.55** makes the cut.

### Real examples from today's feed:

| Headline | Score | Verdict |
|---|---|---|
| Monopoly World Champ Reveals Winning Secrets | 0.981 | ✅ Absolute banger |
| Older Whales More Successful Because Better Singers | 0.979 | ✅ Peak content |
| Astronomers Solve One of Saturn's Greatest Mysteries | 0.970 | ✅ Science wins |
| Fish Biology Inspires Microplastics Cleanup | 0.961 | ✅ Ocean healing |
| Flood damage reported across region | 0.12 | ❌ Not today |
| City officials debate new tax proposal | 0.41 | ❌ Hard pass |

---

## 🏗️ Architecture

```
                        THE WORLD
                    (lots of bad news)
                           │
              ┌────────────▼────────────┐
              │      8 RSS FEEDS        │
              │  Good News Network      │
              │  Positive News          │
              │  BBC Science & Health   │
              │  NPR · TechCrunch       │
              │  Science Daily          │
              └────────────┬────────────┘
                           │ fetched in parallel every 20 mins
                           ▼
              ┌────────────────────────┐
              │   BACKGROUND JOB       │
              │   (you never see this) │
              │                        │
              │  110 articles in       │
              │       ↓                │
              │  VADER sentiment       │
              │       ↓                │
              │  52 articles out ✨    │
              └────────────┬───────────┘
                           │ stores results
                           ▼
              ┌────────────────────────┐
              │   IN-MEMORY STORE      │
              │   52 happy articles    │
              │   sorted by positivity │
              │   ready and waiting    │
              └────────────┬───────────┘
                           │ <50ms response
                           ▼
              ┌────────────────────────┐
              │   YOU, ON YOUR PHONE   │
              │   opening the app      │
              │   feeling good 😊      │
              └────────────────────────┘
```

---

## 🚀 Run It Yourself

### Prerequisites
- Python 3.9+
- A soul tired of bad news

### Setup

```bash
# Clone it
git clone https://github.com/dhanashree23112003/good-news-app
cd good-news-app

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

# Install dependencies (takes 30 seconds, not 10 minutes — no PyTorch!)
pip install -r requirements.txt

# Run it
uvicorn main:app --reload
```

### Watch the magic happen in your terminal:
```
✅ VADER sentiment analyzer loaded
🚀 App ready. Background job runs every 20 mins.
🔄 Background job started...
Fetched 15 articles from Good News Network
Fetched 15 articles from TechCrunch
Fetched 10 articles from NPR News
... (all 8 feeds in parallel)
Total fetched: 110 articles
New articles: 110 | Already seen: 0
✅ Done in 0.4s | 52 new positive | store total: 52
```

**0.4 seconds.** To fetch and analyze 110 articles. On a potato laptop.

---

## 🔌 API

```
GET /api/news      → the good stuff (instant)
GET /api/status    → is the background job alive?
GET /api/health    → server health
GET /docs          → swagger UI (auto-generated, free)
```

### Parameters
```
?limit=20          how many articles (1-30)
?threshold=0.55    how positive (0.0-1.0)
?refresh=true      trigger a background refresh now
```

### Example response:
```json
{
  "title": "Older Male Whales More Successful at Mating Because They're Better Singers",
  "source": "Good News Network",
  "positive_score": 0.979,
  "url": "https://..."
}
```

Yes, that's a real article. Yes, it passed the filter. Whale karaoke is objectively good news.

---

## 📦 Dependencies

```
fastapi          web framework
uvicorn          server
feedparser       RSS parsing
vaderSentiment   sentiment analysis (~2MB, no GPU, no drama)
apscheduler      background job scheduling
pydantic         data validation
```

**Total install size: ~15MB.**
The old version needed PyTorch (~700MB) and a Gradio Space API call for every single article.
Now it's 15MB and runs on anything with a power button.

---

## 🗺️ What's Next

- [ ] PWA — install it on your home screen like a real app
- [ ] Categories — science / health / environment / tech
- [ ] Daily digest email — good news in your inbox every morning
- [ ] Save favourites
- [ ] Dark mode (for night-time good news reading)
- [ ] Docker one-liner deploy

---

## 🙏 Credits

- [Good News Network](https://www.goodnewsnetwork.org) — the OG good news source
- [Positive News](https://www.positive.news) — journalism that doesn't destroy your will to live
- [VADER Sentiment](https://github.com/cjhutto/vaderSentiment) — the tiny NLP tool that makes it all work
- [FastAPI](https://fastapi.tiangolo.com) — so fast it should be illegal
- [HuggingFace Spaces](https://huggingface.co/spaces) — free hosting that actually works

---

<div align="center">

**Made with ☀️ because the world needs more good news apps and fewer doomscrolling ones.**

*If this made you smile, give it a ⭐*

</div>
