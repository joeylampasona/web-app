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
-- with a password), and this gives it a subscription that no card and no
-- Stripe event is behind. Nothing else grants entitlement this way; the
-- webhook is the only other writer, and it will never write this row because
-- this person has no Stripe customer.
do $$
declare
  -- ------------------------------------------------ CHANGE THIS ONE LINE
  test_email text := 'paywall-selftest@example.com';
  -- ---------------------------------------------------------------------
  uid uuid;
begin
  select id into uid from auth.users where lower(email) = lower(test_email);

  if uid is null then
    raise exception
      'No account exists for %. Create it under Authentication > Users > Add '
      'user (set a password, and tick the box that confirms the address), '
      'then run this file again.', test_email;
  end if;

  insert into public.subscriptions
    (user_id, status, plan_interval, current_period_end, stripe_customer_id)
  values
    (uid, 'active', 'year', timestamptz '2099-01-01 00:00:00+00', null)
  on conflict (user_id) do update
    set status             = 'active',
        plan_interval      = 'year',
        current_period_end = timestamptz '2099-01-01 00:00:00+00',
        updated_at         = now();

  raise notice 'Entitled % (%) until 2099.', test_email, uid;
end $$;

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

-- What you should see: one notice naming the account, and one row affected.
select path, as_of, updated_at
  from public.gated_content
 where path = 'selftest/entitlement.json';
