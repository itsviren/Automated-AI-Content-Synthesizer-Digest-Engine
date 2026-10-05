# Initial development status

## Implemented

RSS/Atom ingestion; bounded article extraction; URL and exact-content deduplication per profile; executive/technical profile prompts; optional Gemini structured summaries; explicit extractive fallback; SQLite and Supabase adapters; transactional completion and run leases; Markdown/HTML exports; read-only responsive dashboard with recent-archive search; JSON API; RSS output; health endpoint; Render blueprint; daily and test GitHub Actions workflows.

## Verified locally

21 offline tests pass. They cover summaries and malformed AI responses, free-quota fallback, normalization, private-network redirects, extraction, deduplication, transactional rollback, expired run leases, retries, API bounds, search, RSS, and HTML escaping. A live no-key pipeline run collected 15 articles from three configured feeds and produced a persisted local digest and exports. A second run reused the existing digest without reprocessing. Dashboard preview uses that real local data; search and mobile layout were checked in the browser. Test output includes a non-failing upstream Starlette TestClient deprecation warning.

## Hosted deployment — October 6, 2026

The initial implementation (29239d0) has been pushed to the repository's `main` branch. The GitHub-hosted Tests workflow completed successfully:

https://github.com/itsviren/Automated-AI-Content-Synthesizer-Digest-Engine/actions/runs/37359470835

Render and Supabase account access is available. A Free Supabase project named `content-digest-engine` has been created (project reference `ufkkzrkpobmcaaxentyp`). The repository schema ran successfully. A live SQL check confirmed row-level security is enabled and anonymous SELECT access is disabled on `articles`, `digests`, and `runs`.

The approved service-role key is configured in Render environment variables and GitHub Actions Secrets, alongside `SUPABASE_URL`. No credentials are committed. An ignored local `.env` also supports development against this project.

The Render Free service in Singapore is live at https://content-digest-engine.onrender.com/ (service ID `srv-db1vcb8m7kps73cvbpd0`). It uses Python 3.12.8, locked dependencies, and `/health`. The first GitHub Actions digest run completed successfully and stored 15 articles in Supabase:

https://github.com/itsviren/Automated-AI-Content-Synthesizer-Digest-Engine/actions/runs/37361563946

Live checks returned HTTP 200 for the dashboard, health endpoint, digest API, RSS feed, Markdown download, and search. A real Supabase-backed rerun reused the existing digest without reprocessing or generating a duplicate. Daily execution is configured for 08:17 IST (02:47 UTC); the scheduled trigger itself will first be exercised at its next scheduled time.

cron-job.org job `8585914` is enabled and points to the Render `/health` URL every ten minutes. Its real test run returned HTTP 200 OK in 312 ms. Failure notifications are configured after three consecutive failures, with recovery and automatic-disable notifications enabled. The existing unrelated cron job was left untouched.

The Render billing page confirms Hobby, two services, no card on file, and 750 shared free instance hours/month (115.02 used at verification). Two continuously awake free services can exhaust the shared allowance; a ten-minute keep-alive does not provide unlimited free uptime. No payment method, paid plan, or paid AI provider was enabled.

## Remaining integration work

Gemini model calls remain unconfigured and unverified. Current summaries explicitly use the extractive fallback, requiring no AI spending. Supabase schema, REST/RPC, Render deployment, manually dispatched GitHub digest execution, and the GitHub test workflow are verified live. Exact future schedule execution and continuous availability are not guaranteed by free providers.

## Later work

PDF and transcript ingestion; semantic deduplication; historical RAG; authenticated source editing; private workspaces; automated retention/backups; email or chat delivery; rigorous fact checking. This release checks summary structure and preserves citations, but does not independently verify source claims.
