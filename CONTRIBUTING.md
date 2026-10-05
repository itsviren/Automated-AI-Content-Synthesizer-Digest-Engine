# Contributing

Use Python 3.11+ and a virtual environment. Install requirements.lock.txt, copy .env.example to .env, and use SQLite for development. Run `python -m pytest -q` before submitting a change.

Branch names use `codex/` for agent work. Keep ingestion, synthesis, persistence, and web presentation separate. Test malformed feed data, AI failures, duplicate execution, and storage failures when those behaviors change. Do not make offline tests depend on provider accounts.

The first release intentionally uses operator-managed feeds and a read-only dashboard. Authenticated settings, transcript/PDF support, vector search, and richer delivery are later phases. Any feature must keep the default deployment within free service plans and bounded AI usage.
