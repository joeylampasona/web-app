-- Base & Breakout — account storage.
--
-- Paste the whole file into the Supabase SQL editor and run it once. It is
-- written to be safe to run again: every statement is guarded, so re-running
-- after a change adds what is missing and leaves the rest alone.
--
-- Two tables, both keyed on the signed-in user. Row-level security is on for
-- both, and every policy is `auth.uid() = user_id`, so the public anon key in
-- the web app can read and write one person's rows and nobody else's. There is
-- no service-role key anywhere in this project, and nothing here needs one.

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
