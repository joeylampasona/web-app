-- Base & Breakout — subscription state.
--
-- Paste the whole file into the Supabase SQL editor and run it once. Like
-- schema.sql it is written to be safe to run again: every statement is
-- guarded, so re-running after a change adds what is missing and leaves the
-- rest alone. Run schema.sql first if you have not.
--
-- This file deliberately contains NO gated content and no Stripe keys. It
-- establishes one thing: who is entitled. The content itself moves behind
-- that entitlement in a later change, and the order matters — the lock is
-- proved before anything of value is put behind it.
--
-- The website never writes to this table. It holds the anon key, and there is
-- no insert, update or delete policy here, so the anon key cannot change
-- anyone's subscription including its owner's. Only Stripe's webhook writes,
-- and it authenticates with the service-role key, which bypasses row-level
-- security and lives in the server environment alone.

-- ------------------------------------------------------------ subscriptions

create table if not exists public.subscriptions (
  -- One row per person, not per subscription. A customer who cancels and
  -- resubscribes is the same person with a new Stripe subscription id, and
  -- keeping one row means the entitlement question has one answer.
  user_id                 uuid primary key
                          references auth.users (id) on delete cascade,
  stripe_customer_id      text unique,
  stripe_subscription_id  text unique,
  -- Stripe's own vocabulary, stored verbatim: trialing, active, past_due,
  -- canceled, incomplete, incomplete_expired, unpaid, paused. Not translated
  -- into a boolean here, because "past_due" and "canceled" are different
  -- situations and a boolean would throw away which one it is.
  status                  text not null default 'none',
  price_id                text,
  -- 'month' or 'year'. Kept so the account page can say what someone bought
  -- without another call to Stripe.
  plan_interval           text,
  current_period_end      timestamptz,
  trial_end               timestamptz,
  cancel_at_period_end    boolean not null default false,
  updated_at              timestamptz not null default now()
);

create index if not exists subscriptions_status_idx
  on public.subscriptions (status);

alter table public.subscriptions enable row level security;

-- Read your own row, and only your own. There is no write policy on purpose:
-- with row-level security on and no policy for insert, update or delete, the
-- anon and authenticated roles cannot write at all. Someone editing the
-- client cannot grant themselves a subscription.
drop policy if exists "you can read your own subscription" on public.subscriptions;
create policy "you can read your own subscription" on public.subscriptions
  for select
  using (auth.uid() = user_id);

-- ------------------------------------------------------------ entitlement

-- The one definition of "is this person paid up", so that policies, server
-- routes and the interface cannot drift apart by each deciding separately.
--
-- security definer so it can read the table regardless of the caller's own
-- policies, and search_path pinned so the body cannot be hijacked by a
-- caller-controlled schema. It takes no caller-supplied user id: it answers
-- only for whoever is asking, which removes the possibility of a route being
-- talked into asking about somebody else.
create or replace function public.is_subscriber()
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.subscriptions s
    where s.user_id = auth.uid()
      -- past_due is deliberately included. A card that failed this morning is
      -- a billing problem, not a reason to lock someone out of something they
      -- have paid for all year; Stripe moves them to canceled or unpaid when
      -- it gives up, and those are excluded.
      and s.status in ('trialing', 'active', 'past_due')
      -- A period end in the past means Stripe has not told us anything since
      -- it lapsed. Treat silence as expired rather than as still valid.
      and (s.current_period_end is null or s.current_period_end > now())
  );
$$;

revoke all on function public.is_subscriber() from public;
grant execute on function public.is_subscriber() to authenticated, anon;

comment on function public.is_subscriber() is
  'True when the caller has a live subscription or trial. The single source of '
  'truth for entitlement; policies and server routes both use it.';
