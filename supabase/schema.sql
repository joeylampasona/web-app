-- Base & Breakout — account storage.
--
-- Paste the whole file into the Supabase SQL editor and run it once. It is
-- written to be safe to run again: every statement is guarded, so re-running
-- after a change adds what is missing and leaves the rest alone.
--
-- Two tables, both keyed on the signed-in user. Row-level security is on for
-- both, and every policy is `auth.uid() = user_id`, so the public anon key in
-- the web app can read and write one person's rows and nobody else's. There is
-- no service-role key in the website, and nothing the website does needs one.
-- The weekly digest job is the one exception: it runs in CI, reads every
-- opted-in address, and therefore uses a service-role key held in GitHub
-- Actions secrets. It is never exposed to the browser and never carries a
-- NEXT_PUBLIC_ prefix. Unsubscribing deliberately does NOT use it -- that runs
-- through unsubscribe_by_token() below, so the public site still needs nothing
-- but the anon key.

-- ---------------------------------------------------------------- watchlist
create table if not exists public.watchlist (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  symbol      text not null check (symbol = upper(symbol) and length(symbol) between 1 and 12),
  created_at  timestamptz not null default now(),
  -- The same ticker twice is a double-tap, not two holdings.
  unique (user_id, symbol)
);

create index if not exists watchlist_user_created_idx
  on public.watchlist (user_id, created_at);

alter table public.watchlist enable row level security;

drop policy if exists "watchlist is private" on public.watchlist;
create policy "watchlist is private" on public.watchlist
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- 50 tickers is the published limit. The web app stops at 50; this stops a
-- client that has been edited from writing the 51st.
create or replace function public.watchlist_cap() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if (select count(*) from public.watchlist where user_id = new.user_id) >= 50 then
    raise exception 'A watchlist holds 50 tickers. Remove one to add another.';
  end if;
  return new;
end;
$$;

drop trigger if exists watchlist_cap_trigger on public.watchlist;
create trigger watchlist_cap_trigger
  before insert on public.watchlist
  for each row execute function public.watchlist_cap();

-- ------------------------------------------------------------ saved screens
create table if not exists public.saved_screens (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  name        text not null check (length(trim(name)) between 1 and 60),
  -- Which detector the dials belong to. Dials are not portable between them.
  -- The allowed list is set below rather than inline, so that adding a screen
  -- is a re-run of this file rather than a hand-written ALTER.
  screen      text not null,
  -- The dial positions, exactly as the panel holds them.
  values      jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  unique (user_id, name)
);

-- Named, dropped and re-added, so running this file again after a screen is
-- added widens the constraint instead of failing on "already exists". An
-- existing project picks up new screens by re-running this file, nothing else.
alter table public.saved_screens drop constraint if exists saved_screens_screen_check;
alter table public.saved_screens add constraint saved_screens_screen_check
  check (screen in ('vcp', 'blue_sky', 'multi_year', 'ipo',
                    'flat_base', 'cup_and_handle'));

create index if not exists saved_screens_user_created_idx
  on public.saved_screens (user_id, created_at desc);

alter table public.saved_screens enable row level security;

drop policy if exists "saved screens are private" on public.saved_screens;
create policy "saved screens are private" on public.saved_screens
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create or replace function public.saved_screens_cap() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if (select count(*) from public.saved_screens where user_id = new.user_id) >= 20 then
    raise exception 'That is 20 saved screens, the limit. Delete one to save another.';
  end if;
  return new;
end;
$$;

drop trigger if exists saved_screens_cap_trigger on public.saved_screens;
create trigger saved_screens_cap_trigger
  before insert on public.saved_screens
  for each row execute function public.saved_screens_cap();

-- ------------------------------------------------------------- email prefs
-- One row per account, holding whether they want mail and the token that lets
-- them stop it without signing in.
--
-- An account is not consent. Both flags default to false and only the person
-- can turn them on, which is why consented_at is recorded: if anyone ever asks
-- whether there was permission, the answer has to be a row, not a memory.
--
-- The address is denormalised out of auth.users by the trigger below. The
-- sending job then reads one table in the public schema instead of reaching
-- into the auth schema, and the trigger keeps it true when someone changes
-- their address.
create table if not exists public.email_prefs (
  user_id           uuid primary key references auth.users (id) on delete cascade,
  email             text not null,
  weekly_digest     boolean not null default false,
  watchlist_alerts  boolean not null default false,
  -- Random, unguessable, and the only thing an unsubscribe link carries.
  unsubscribe_token uuid not null default gen_random_uuid() unique,
  consented_at      timestamptz,
  consent_ip        text,
  -- Mail that keeps bouncing costs the domain its reputation, and the sign-in
  -- codes go out over the same domain. A few bounces and this address is
  -- switched off before it can do that damage.
  bounce_count      integer not null default 0,
  disabled_at       timestamptz,
  disabled_reason   text,
  -- Makes a re-run idempotent: a job that half-finished can be run again
  -- without sending twice to whoever it already reached.
  last_sent_at      timestamptz,
  created_at        timestamptz not null default now()
);

create index if not exists email_prefs_digest_idx
  on public.email_prefs (weekly_digest) where disabled_at is null;

alter table public.email_prefs enable row level security;

-- The same rule as every other table: you see your row and nobody else's.
-- The sending job does not go through this; it uses a service-role key, which
-- bypasses RLS by design and lives only in CI secrets.
drop policy if exists "email prefs are private" on public.email_prefs;
create policy "email prefs are private" on public.email_prefs
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- A row for every account, created with both flags off.
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.email_prefs (user_id, email)
  values (new.id, new.email)
  on conflict (user_id) do update set email = excluded.email;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

drop trigger if exists on_auth_user_email_changed on auth.users;
create trigger on_auth_user_email_changed
  after update of email on auth.users
  for each row when (old.email is distinct from new.email)
  execute function public.handle_new_user();

-- Backfill for accounts that existed before this table did.
insert into public.email_prefs (user_id, email)
select id, email from auth.users
on conflict (user_id) do nothing;

-- Unsubscribing must not require signing in. Requiring a login to stop mail is
-- both hostile and non-compliant, and the person clicking may be reading on a
-- device that has never been signed in.
--
-- security definer so the anon key can call it, but it takes only a token and
-- returns only whether it matched. It cannot be used to read an address, find
-- out whether one is registered, or change anything but the flags on the one
-- row whose token was supplied.
create or replace function public.unsubscribe_by_token(token uuid)
returns boolean
language plpgsql security definer set search_path = public as $$
declare
  hit integer;
begin
  update public.email_prefs
     set weekly_digest = false,
         watchlist_alerts = false,
         disabled_at = now(),
         disabled_reason = 'unsubscribed'
   where unsubscribe_token = token;
  get diagnostics hit = row_count;
  return hit > 0;
end;
$$;

revoke all on function public.unsubscribe_by_token(uuid) from public;
grant execute on function public.unsubscribe_by_token(uuid) to anon, authenticated;
