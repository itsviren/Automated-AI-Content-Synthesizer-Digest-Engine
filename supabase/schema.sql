-- Run in Supabase's SQL editor. Repeatable for the initial schema.
create table if not exists public.articles (
    profile text not null,
    url text not null,
    content_hash text not null,
    title text not null,
    category text not null,
    excerpt text not null,
    created_at timestamptz not null default now(),
    primary key (profile, url)
);
create index if not exists articles_hash on public.articles(profile, content_hash);
create table if not exists public.digests (
    id text primary key,
    day date not null,
    profile text not null,
    created_at timestamptz not null default now(),
    payload jsonb not null
);
create table if not exists public.runs (
    id text primary key,
    token uuid not null,
    status text not null check (status in ('running', 'completed', 'failed')),
    updated_at timestamptz not null default now(),
    lease_until timestamptz not null,
    error text
);
alter table public.articles enable row level security;
alter table public.digests enable row level security;
alter table public.runs enable row level security;
revoke all on public.articles, public.digests, public.runs from anon, authenticated;
grant all on public.articles, public.digests, public.runs to service_role;

create or replace function public.claim_digest(p_id text, p_token uuid)
returns text language plpgsql security invoker set search_path = public as $$
declare current_run public.runs;
begin
    perform pg_advisory_xact_lock(hashtextextended(p_id, 0));
    if exists (select 1 from public.digests where id = p_id) then
        return 'completed';
    end if;
    select * into current_run from public.runs where id = p_id for update;
    if found and current_run.status = 'running' and current_run.lease_until > now() then
        return 'busy';
    end if;
    insert into public.runs(id, token, status, updated_at, lease_until)
    values(p_id, p_token, 'running', now(), now() + interval '35 minutes')
    on conflict(id) do update set token = excluded.token, status = 'running',
        updated_at = now(), lease_until = excluded.lease_until, error = null;
    return 'claimed';
end;
$$;

create or replace function public.complete_digest(p_digest jsonb, p_articles jsonb, p_token uuid)
returns void language plpgsql security invoker set search_path = public as $$
declare current_run public.runs;
begin
    select * into current_run from public.runs where id = p_digest->>'id' for update;
    if not found or current_run.token <> p_token or current_run.status <> 'running'
        or current_run.lease_until <= now() then
        raise exception 'Run lease lost';
    end if;
    insert into public.articles(profile, url, content_hash, title, category, excerpt, created_at)
    select x.profile, x.url, x.content_hash, x.title, x.category, x.excerpt, x.created_at
    from jsonb_to_recordset(p_articles) as x(profile text, url text, content_hash text,
        title text, category text, excerpt text, created_at timestamptz)
    on conflict(profile, url) do nothing;
    insert into public.digests(id, day, profile, created_at, payload)
    values(p_digest->>'id', (p_digest->>'day')::date, p_digest->>'profile',
        (p_digest->>'created_at')::timestamptz, p_digest);
    update public.runs set status = 'completed', updated_at = now()
    where id = p_digest->>'id' and token = p_token;
end;
$$;
revoke all on function public.claim_digest(text, uuid) from public, anon, authenticated;
revoke all on function public.complete_digest(jsonb, jsonb, uuid) from public, anon, authenticated;
grant execute on function public.claim_digest(text, uuid) to service_role;
grant execute on function public.complete_digest(jsonb, jsonb, uuid) to service_role;
