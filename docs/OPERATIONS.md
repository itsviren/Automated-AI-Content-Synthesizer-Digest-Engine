# Operations

## Routine checks

- GitHub Actions: daily digest completed, artifacts available, schedule enabled.
- Dashboard: latest digest date, visible fallback method, source links and warnings.
- Supabase: runs status, free storage/egress usage, project activity.
- cron-job.org: `/health` checks and failure notification settings.

The health endpoint checks process liveness only; it does not verify storage or digest completion. A successful keep-alive request does not prove the daily pipeline succeeded.

## Retry and recovery

Manually dispatch the Daily digest workflow for the desired profile. Completed date/profile pairs are re-exported without calling AI again. Failed runs can be retried immediately. A killed process holds its lease for at most 35 minutes; wait for that lease to expire before retrying. The GitHub job is capped at 30 minutes.

Storage completion writes articles, digest, and run status in one transaction. If export fails after completion, rerun to regenerate exports from stored data. If every feed fails, the job fails rather than publishing an empty success. A valid feed with no new articles can produce an empty edition.

## Limits and maintenance

The initial limits are 20 articles/run, 5 entries/feed, and 20 AI requests/run including retries. A quota error switches remaining items to extractive summaries. No paid fallback is configured. Summaries are capped at 1000 characters; article excerpts stored in the database are capped at 1000 characters.

The web archive displays the latest 30 editions. The JSON API supports up to 100 per request. Long-term pagination, automated database retention, and backups are not implemented in this initial release. Monitor capacity and export/prune historical data before Supabase's free storage is exhausted.

## Account setup still required

Run supabase/schema.sql on a Free project, add GitHub secrets, deploy Render, and configure cron-job.org. Validate each hosted integration after credentials exist. Free plans and AI model availability must be checked at setup time.
