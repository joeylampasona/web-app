-- Base & Breakout — the fixture that makes the paywall check mean something.
--
-- Run this once, in the Supabase SQL editor, after paywall.sql. Change the
-- email on the line marked below to the address of the test account first.
--
-- Why this exists.
--
-- The check in CI asks for gated content as an outsider and fails if anything
-- comes back. That sounds like proof and is not, on its own: if the table were
-- empty, or the policy denied everybody including subscribers, or the table
-- had been dropped altogether, every one of those requests would come back
-- empty and the check would pass. It measures silence, and silence is what a
-- broken paywall and a working one have in common.
--
-- Two rows fix that. One account that is permanently entitled, and one row of
-- content that definitely exists. Then the same path can be asked for twice —
-- once by that account, once by an outsider — and the two answers have to
-- differ. A dropped table, a policy that denies everyone, an empty table: each
-- now fails the first half. A policy that grants everyone fails the second.
--
-- The sentinel content is worthless on purpose. It is readable by every
-- subscriber, so it must not be anything a subscriber is paying for.

-- --------------------------------------------------- a permanently paid user
--
-- The account is created in the dashboard (Authentication > Users > Add user,
-- with a password), and this comps it. No card and no Stripe event is behind
-- it; the webhook is the only other writer and it never touches the comp
-- column, so nothing can take this away by accident.
-- Through grant_lifetime, the same path a comped person goes through, so the
-- check exercises the real mechanism rather than a fixture that resembles it.
-- A date far in the future would have worked and would have quietly stopped
-- testing the comp branch of is_subscriber().
select * from public.grant_lifetime(
  -- ------------------------------------------------ CHANGE THIS ONE LINE
  'paywall-selftest@example.com',
  -- ---------------------------------------------------------------------
  'Fixture for the CI paywall check.');

-- ------------------------------------------------------- the sentinel content
--
-- Deliberately empty of value. Its whole job is to be a row that exists, so
-- that "no rows" from an outsider is a decision the policy made rather than an
-- absence it never had to rule on.
insert into public.gated_content (path, payload, as_of)
values (
  'selftest/entitlement.json',
  jsonb_build_object(
    'note', 'Fixture for the paywall check. Contains nothing of value.',
    'granted', true
  ),
  current_date
)
on conflict (path) do update
  set payload    = excluded.payload,
      as_of      = current_date,
      updated_at = now();

-- What you should see: one row from grant_lifetime showing comped = true, and
-- one row below naming the sentinel.
select path, as_of, updated_at
  from public.gated_content
 where path = 'selftest/entitlement.json';
