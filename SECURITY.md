# Security

## Credentials

Never commit .env files, Supabase service-role keys, or Gemini keys. Supabase keys are server-only. GitHub Actions stores credentials as Secrets. RLS and restricted function permissions prevent browser clients from writing tables directly.

## Source content

Operators should configure trusted public RSS feeds. Requests reject non-public DNS results, validate redirect destinations, restrict ports, and bound response sizes. This is not a sandbox for arbitrary user-provided URLs; DNS rebinding and hostile scraping targets require additional network isolation before opening feed management to users.

Article text can contain prompt injection. The model is instructed to treat it as data, and generated output is structurally validated. This is not a factual accuracy guarantee. Model output cannot execute tools or choose destination URLs. HTML templates and exports escape source content.

## Public dashboard

All published digests are public. Only ingest public material in this release. Do not connect private newsletters or internal documents without adding authentication and reviewing the AI provider's data-use terms.

## Reporting

Do not post credentials or sensitive source content in public GitHub issues. Rotate exposed credentials in the relevant provider account and remove access before investigating. The application intentionally has no public digest-trigger endpoint.
