# Development plan

## Initial deliverable

- [x] RSS and public web ingestion, text cleaning, URL/content deduplication.
- [x] Executive and technical profiles with source-linked summaries.
- [x] Optional Gemini synthesis and no-key extractive fallback.
- [x] SQLite local adapter and Supabase production adapter.
- [x] Dashboard, JSON digest API, health check, RSS output.
- [x] Markdown and HTML exports.
- [x] GitHub Actions tests and daily digest workflow.
- [x] Supabase schema, Render blueprint, deployment instructions.
- [x] Offline tests for deduplication, fallbacks, persistence, and web rendering.

Implementation is complete for this initial scope. Hosted integration verification remains pending account setup; see STATUS.md.

## Later phases

PDF ingestion; existing YouTube/podcast transcripts; authenticated feed management; retention tools; semantic deduplication and historical search. Audio transcription, browser scraping, email delivery, and automatic fact verification are outside the first release.

## Free budget rules

Start with 20 articles per day, at most 5 per feed, one daily execution, and a 30-minute Actions timeout. Use no paid model fallback, paid Render cron, persistent Render disk, Redis, or paid domain. Free quotas and availability can change. Provider setup must select free plans; no payment-enabled overage should be configured.
