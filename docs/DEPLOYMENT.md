# Free deployment

Current live dashboard: https://content-digest-engine.onrender.com/

The setup below is already configured for this repository. Consult STATUS.md before creating resources, to avoid duplicating the existing Supabase project, Render service, or cron-job.org job.

## 1. Supabase

Create a Free project. Run `supabase/schema.sql` in the SQL editor. Keep the project URL and service-role key in server secrets. Do not expose the key in frontend JavaScript or commit it. The schema enables row-level security; the dashboard talks to Supabase server-side.

## 2. GitHub

Push this repository. Add Actions secrets `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and optionally `GEMINI_API_KEY`. Set repository variable `GEMINI_MODEL` to a currently available free-tier text model if using AI. With no key, the pipeline uses extractive summaries.

The daily workflow runs at 02:47 UTC / 08:17 IST. It also supports manual dispatch. It executes Python directly rather than calling Render. Standard runners are free for public repositories; private repositories have included-minute limits. Scheduled jobs can be delayed and public schedules can be disabled after 60 days without activity.

## 3. Render

Connect the repository and deploy `render.yaml`, or create a Free web service manually. Build command: `pip install -r requirements.lock.txt`. Start command: `uvicorn src.app:app --host 0.0.0.0 --port $PORT`.

Set `STORAGE_BACKEND=supabase`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`. No Gemini key is needed on Render because synthesis runs in Actions. Use the provider's free subdomain. Do not use local SQLite in production.

## 4. cron-job.org

Create a GET job for `https://YOUR-SERVICE.onrender.com/health`, every ten minutes, and enable failure notifications. This is only a keep-alive check. Its request success does not imply the digest succeeded; inspect GitHub Actions and stored run history. A cold service may still timeout initially.

## Validation

Run the test workflow; manually run the daily workflow; confirm digest rows in Supabase and output artifacts; check `/health`, `/api/digests`, `/rss.xml`, and the dashboard. Rerun the same profile/date and verify there is no duplicate digest. Never place credentials in logs or screenshots.

## Operations

Review free quota dashboards. Supabase Free can pause inactive projects and does not include automatic backups. Keep only bounded article excerpts, periodically export data, and plan retention before approaching database capacity. Cron-job.org is not a guaranteed uptime mechanism. Render can restart free services. Configure AI billing as disabled and check current free model availability before enabling AI.
