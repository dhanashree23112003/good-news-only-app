# ☀️ Good News Only

A **mobile-friendly web app** that shows only positive, uplifting news — powered by AI sentiment analysis running entirely on your local machine. No API keys. No paid services. No tracking.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        BROWSER                              │
│   frontend/index.html                                       │
│   ┌──────────────────────────────────────────────────────┐  │
│   │  Renders cards · Source filter · Threshold slider    │  │
│   │  Calls /api/news every load                          │  │
│   └────────────────────┬─────────────────────────────────┘  │
└────────────────────────┼────────────────────────────────────┘
                         │ HTTP GET /api/news
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  FASTAPI BACKEND (Python)                    │
│                                                             │
│  ┌──────────────┐    ┌───────────────┐    ┌─────────────┐  │
│  │  RSS Fetcher │───►│ Sentiment NLP │───►│   Filter    │  │
│  │  (feedparser)│    │  (HuggingFace)│    │ score≥0.55  │  │
│  └──────────────┘    └───────────────┘    └──────┬──────┘  │
│                                                  │          │
│  ┌──────────────────────────────────────────┐    │          │
│  │  In-memory cache (15min TTL)             │◄───┘          │
│  └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────────┐
│                  FREE RSS FEEDS (no keys)                    │
│  Good News Network · Positive.News · NPR                    │
│  BBC Science · BBC Health · ScienceDaily · TechCrunch       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧠 How Sentiment Filtering Works

**Model:** `cardiffnlp/twitter-roberta-base-sentiment-latest`
- A RoBERTa model fine-tuned on 58 million tweets
- Outputs three scores (0.0–1.0) for: **positive**, **neutral**, **negative**
- Runs locally via HuggingFace Transformers — no API calls, no internet after first download

**What gets analyzed:**
```
headline text + first 200 chars of summary
```
The headline captures tone most reliably. The summary adds context for edge cases.

**The filter:**
```python
if positive_score >= 0.55:  # configurable via slider
    include_article()
```

**Default threshold: 0.55**
- Below 0.55: too many neutral/negative stories slip through
- Above 0.75: very strict, may filter too aggressively
- The frontend slider lets users tune this live

**Example scores:**
```
"Scientists discover cancer treatment breakthrough"  → 0.89 ✅ PASS
"Baby panda born at zoo"                            → 0.92 ✅ PASS
"Community garden transforms abandoned lot"         → 0.78 ✅ PASS
"City officials debate new tax proposal"            → 0.41 ❌ SKIP
"Flood damage reported across region"               → 0.12 ❌ SKIP
```

---

## 📁 File Structure

```
goodnews/
├── backend/
│   ├── main.py              # FastAPI app (all backend logic)
│   └── requirements.txt     # Python dependencies
├── frontend/
│   └── index.html           # Complete frontend (single file)
├── setup.sh                 # One-time setup script
└── README.md
```

---

## 🚀 Setup & Run (Step by Step)

### Prerequisites
- Python 3.9 or higher
- ~1.5GB disk space (for PyTorch + model cache)
- Internet connection (for first model download + RSS feeds)

---

### Step 1 — Clone / Download
```bash
# If from a zip:
unzip goodnews.zip
cd goodnews
```

### Step 2 — Create a Virtual Environment
```bash
cd backend
python3 -m venv venv
```

### Step 3 — Activate It
```bash
# macOS / Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```
You'll see `(venv)` in your terminal prompt.

### Step 4 — Install Dependencies
```bash
pip install -r requirements.txt
```
⏳ This takes **3–10 minutes** on first run. PyTorch is large (~700MB).

### Step 5 — Start the Backend
```bash
uvicorn main:app --reload
```
You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Loading sentiment model…
INFO:     Sentiment model loaded ✓
```

> **First run:** The model downloads ~500MB to `~/.cache/huggingface/`. Every run after is instant.

### Step 6 — Open the Frontend
Simply open `frontend/index.html` in your browser:
```bash
# macOS:
open ../frontend/index.html

# Linux:
xdg-open ../frontend/index.html

# Windows:
start ../frontend/index.html
```

Or drag the `index.html` file into Chrome/Firefox.

---

## 🔌 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/news` | Returns filtered positive articles |
| `GET /api/stats` | Filter rates and model info |
| `GET /api/health` | Backend health check |
| `GET /docs` | Auto-generated Swagger UI |

### Query Parameters for `/api/news`
| Param | Default | Range | Description |
|-------|---------|-------|-------------|
| `limit` | 20 | 1–30 | Max articles to return |
| `threshold` | 0.55 | 0.0–1.0 | Min positive sentiment score |
| `refresh` | false | bool | Bypass cache, force re-fetch |

**Example:**
```
http://localhost:8000/api/news?threshold=0.7&limit=10
```

---

## 🎛️ Customization

### Add more RSS feeds
In `backend/main.py`, add to the `RSS_FEEDS` list:
```python
{"url": "https://yourfeed.com/rss", "source": "Your Source"},
```

### Change the positivity threshold
In `backend/main.py`:
```python
POSITIVE_THRESHOLD = 0.65  # higher = stricter
```
Or use the slider in the frontend without restarting.

### Use a different sentiment model
Replace the model in `main.py`:
```python
sentiment_pipeline = pipeline(
    task="sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",  # smaller, faster
    ...
)
```
Note: different models use different label names — check the `analyze_sentiment()` function if switching.

### Convert to PWA
1. Create `frontend/manifest.json` with app metadata
2. Add `<link rel="manifest">` in index.html (commented line is already there)
3. Add a `service-worker.js` for offline caching

---

## 🐛 Troubleshooting

**"Could not load news" error in the browser**
→ Make sure the backend is running: `uvicorn main:app --reload`

**First load takes 60+ seconds**
→ The model is downloading (one-time). After download, it loads in ~5 seconds.

**"No articles found" with high threshold**
→ Lower the threshold slider. At 0.9+ very few articles pass.

**CORS error in browser console**
→ Make sure you're opening `index.html` from the file system (not a different server).
   If using a local dev server, update `API_BASE` in `index.html` to match.

**Model label mismatch / all scores are 0**
→ Some model versions use different label names. Print `results` in `analyze_sentiment()` to inspect.

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `feedparser` | RSS/Atom feed parsing |
| `transformers` | HuggingFace NLP models |
| `torch` | PyTorch (runs the model) |
| `httpx` | Async HTTP client |
| `pydantic` | Data validation |

---

## 🗺️ Roadmap

- [ ] PWA manifest + service worker (offline support)
- [ ] Save favorite articles (localStorage)
- [ ] Email digest option
- [ ] Topic categories (science, health, environment...)
- [ ] User-defined keyword allowlist/blocklist
- [ ] Switch to lighter model (DistilBERT) for faster startup
- [ ] Docker container for one-command deploy
