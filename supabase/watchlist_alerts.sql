-- Watchlist alerts: what has already been sent, so nothing is sent twice.
--
-- Paste into the Supabase SQL editor after schema.sql and paywall.sql. Safe to
-- run again.
--
-- The intraday quotes job checks every subscriber's watchlist every fifteen
-- minutes during the session. Without a record, a stock sitting above its
-- pivot all afternoon would produce an email every fifteen minutes. One row
-- per person, stock, kind of event and session: the job inserts the rows it
-- wants to send with "ignore duplicates", and sends only the ones that were
-- new. Two overlapping runs cannot both win the same row.
create table if not exists public.watchlist_alert_log (
  user_id  uuid not null references auth.users (id) on delete cascade,
  symbol   text not null,
  -- crossed: a long setup traded through its pivot.
  -- near:    a long setup within a small distance under its pivot.
  -- broke:   a short setup (a breakdown) traded through its level.
  kind     text not null check (kind in ('crossed', 'near', 'broke')),
  session  date not null,
  screen   text,
  sent_at  timestamptz not null default now(),
  primary key (user_id, symbol, kind, session)
);

create index if not exists watchlist_alert_log_session_idx
  on public.watchlist_alert_log (session);

-- Written and read only by the job, with the service-role key, which bypasses
-- RLS. RLS on with no policies means the browser cannot read or write it at
-- all, not even a person's own rows: nothing on the site needs them.
alter table public.watchlist_alert_log enable row level security;

-- Rows older than thirty days are deleted by the job itself, through the same
-- service-role REST call it uses for everything else, so there is no function
-- here to grant or keep in step.
