# Automated AI Content Synthesizer & Digest Engine

A daily digest service that gathers RSS articles, removes duplicates, creates source-linked summaries, and publishes a searchable web archive.

**Live dashboard:** https://content-digest-engine.onrender.com/

## Agreed deployment

- GitHub: source, tests, and scheduled Python execution through Actions.
- Render Free: FastAPI dashboard and read-only API.
- Supabase Free: persistent PostgreSQL data through its REST API.
- cron-job.org: GET `/health` every ten minutes; no digest execution.
- Gemini: optional free-tier text generation. Extractive summaries work without an AI key.

Start with [development plan](docs/DEVELOPMENT.md), [architecture](docs/ARCHITECTURE.md), and [deployment instructions](docs/DEPLOYMENT.md).

## Local development

Use Python 3.11 or newer:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.lock.txt
cp .env.example .env
python main.py --profile executive
uvicorn src.app:app --reload
```

Open http://localhost:8000. Local development uses SQLite; production must use Supabase because Render's local disk is ephemeral. Both the CLI and web app load `.env`.

```bash
python -m pytest
```

The hosted deployment uses Render Free and Supabase Free. GitHub Actions generates the executive digest daily at 08:17 IST (02:47 UTC); cron-job.org pings `/health` every ten minutes. Gemini is optional and is not configured in the current deployment, which uses source excerpts. See docs/STATUS.md for live verification evidence.

`requirements.txt` describes allowed dependency ranges; `requirements.lock.txt` captures the versions tested for this release. Use the lock file for reproducible installs and review it when upgrading dependencies.
