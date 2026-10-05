# Project working instructions

## Scope and stack

This project has a strict zero-spend infrastructure requirement. Use Python, FastAPI, Supabase Free, Render Free, GitHub Actions for daily pipeline execution, and cron-job.org only for health pings. Do not substitute paid Render cron jobs or paid AI fallbacks.

## Repository conventions

Read README.md and docs/ARCHITECTURE.md before significant changes. Keep source configuration in config/feeds.json. Local storage may use SQLite; hosted storage must use Supabase. Credentials belong in ignored .env files or provider secrets, never code or frontend assets.

Keep pipeline logic separate from the web process. Preserve profile/date idempotency, atomic completion, and resumable failure behavior. Validate external URLs and redirects; treat article text and model output as untrusted data. Source links are created by ingestion rather than invented by an LLM.

## Validation

Use `.venv/Scripts/python.exe -m pytest -q` on Windows or `.venv/bin/python -m pytest -q` on Unix. Add tests for changed pipeline/storage behavior. Network-independent tests must not use real feeds or AI credentials. Verify the web UI after template or styling changes.

Update deployment instructions when environment variables or provider configuration change. Report hosted integrations as unverified until tested with real configured accounts. Avoid printing secrets, raw AI responses, or provider authentication headers.
