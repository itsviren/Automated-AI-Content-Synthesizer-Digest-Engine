# Architecture

## Execution boundaries

GitHub Actions checks out the repository, installs Python dependencies, runs the digest CLI, writes data to Supabase, and uploads Markdown/HTML outputs as short-lived artifacts. Render serves the dashboard and reads that same database. cron-job.org only calls the health endpoint.

The pipeline does not depend on the Render process being awake. Keep-alive requests can reduce idle sleep but cannot prevent provider restarts or guarantee uptime.

## Data flow

1. Read source configuration; fetch RSS/Atom feeds with bounded timeouts.
2. Limit entries per source and total articles per run.
3. Extract public article text; fall back to feed text if extraction fails.
4. Normalize links and hash content; skip previously processed URLs/content.
5. Generate structured summaries using a configurable Gemini model or an explicit extractive fallback.
6. Preserve source URLs outside model generation; reject malformed AI output.
7. Persist the digest and article identifiers atomically via a Supabase database function.
8. Export Markdown and escaped HTML.

## Storage and safety

SQLite is local-only. Supabase stores articles, digests, and run history. Only trusted server processes receive the service-role key. Enable RLS with no anonymous table access. The public API serves digest output, not credentials or raw private source data.

Feeds must be trusted operator configuration. Article fetching rejects non-public addresses and validates each redirect. Summaries are untrusted content: templates autoescape it. Article text is data, never instructions. Citations establish provenance, not independent factual verification.

## Reliability

Daily digest keys include date and profile. A database lease rejects simultaneous runs; a completed digest is not regenerated on retry. Failed or expired runs can be retried. Database completion is atomic. Exports can be regenerated from persisted output. Individual feed/article failures are logged; total source failure fails the job.

Use bounded network retries and cap AI calls. If free AI quota is unavailable, use extractive output and label its method. No paid-provider fallback exists.
