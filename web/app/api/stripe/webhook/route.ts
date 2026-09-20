import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { verifyStripeSignature } from "@/lib/stripeSignature";

/**
 * Stripe tells us who is paid up.
 *
 * This is the only writer of `subscriptions`, and it writes with the
 * service-role key, which bypasses every policy in the database. So the
 * signature check above it is not a formality — it is the whole boundary. A
 * forged POST that got past it would be a free subscription for anybody who
 * can find the URL.
 *
 * Everything here is written to be safe to receive twice, because Stripe
 * retries on any non-2xx and will happily deliver the same event again. Every
 * write is an upsert keyed on the user, so a replay of a delivered event
 * writes the same row again rather than a second subscription.
 */
export const dynamic = "force-dynamic";
// The raw bytes are what was signed. Next must not parse or re-encode them.
export const runtime = "nodejs";

const PROJECT_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;
const STRIPE_KEY = process.env.STRIPE_SECRET_KEY;

const HANDLED = new Set([
  "checkout.session.completed",
  "customer.subscription.created",
  "customer.subscription.updated",
  "customer.subscription.deleted",
]);

/** Pull the Supabase user id off whatever shape the event carries. */
function userIdFrom(object: Record<string, any>): string | null {
  return object?.metadata?.user_id
    ?? object?.client_reference_id
    ?? null;
}

async function stripeGet(path: string): Promise<any | null> {
  if (!STRIPE_KEY) return null;
  const response = await fetch(`https://api.stripe.com/v1/${path}`, {
    headers: { Authorization: `Bearer ${STRIPE_KEY}` },
  });
  return response.ok ? response.json() : null;
}

export async function POST(request: Request) {
  if (!PROJECT_URL || !SERVICE_KEY || !WEBHOOK_SECRET) {
    console.error("stripe webhook is not configured");
    return NextResponse.json({ error: "not configured" }, { status: 503 });
  }

  // Raw, before anything touches it. Re-serialising a parsed object changes
  // the bytes and the signature will not match.
  const raw = await request.text();
  const verdict = verifyStripeSignature(
    raw, request.headers.get("stripe-signature"), WEBHOOK_SECRET,
  );
  if (!verdict.ok) {
    console.warn("stripe webhook rejected:", verdict.reason);
    // 400, not 401: Stripe stops retrying a 400 and keeps retrying a 401,
    // and a forgery should not be retried at us indefinitely.
    return NextResponse.json({ error: "bad signature" }, { status: 400 });
  }

  let event: any;
  try {
    event = JSON.parse(raw);
  } catch {
    return NextResponse.json({ error: "bad body" }, { status: 400 });
  }

  if (!HANDLED.has(event?.type)) {
    // 200, so Stripe stops sending it. An unhandled type is not an error.
    return NextResponse.json({ received: true, handled: false });
  }

  const object = event?.data?.object ?? {};
  let subscription = object;

  // A completed checkout carries the session, not the subscription. Fetch the
  // subscription so the stored period and status are Stripe's, not inferred.
  if (event.type === "checkout.session.completed") {
    const id = typeof object.subscription === "string" ? object.subscription : null;
    const fetched = id ? await stripeGet(`subscriptions/${id}`) : null;
    if (fetched) subscription = { ...fetched, client_reference_id: object.client_reference_id };
  }

  const userId = userIdFrom(subscription) ?? userIdFrom(object);
  if (!userId) {
    // Nothing to attach it to. 200 so it is not retried forever, and loud so
    // it is not silent: this means a subscription exists in Stripe that this
    // site cannot connect to an account, which someone has paid for.
    console.error("stripe webhook: no user_id on", event.type, event.id);
    return NextResponse.json({ received: true, handled: false });
  }

  const admin = createClient(PROJECT_URL, SERVICE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const seconds = (value: unknown) =>
    typeof value === "number" ? new Date(value * 1000).toISOString() : null;

  const { error } = await admin.from("subscriptions").upsert({
    user_id: userId,
    stripe_customer_id: typeof subscription.customer === "string"
      ? subscription.customer : null,
    stripe_subscription_id: typeof subscription.id === "string"
      && subscription.id.startsWith("sub_") ? subscription.id : null,
    // Stripe's own word for it, stored as given. A deleted subscription
    // arrives with status 'canceled' already, so there is nothing to invent.
    status: subscription.status ?? "none",
    price_id: subscription.items?.data?.[0]?.price?.id ?? null,
    plan_interval: subscription.items?.data?.[0]?.price?.recurring?.interval ?? null,
    current_period_end: seconds(subscription.current_period_end),
    trial_end: seconds(subscription.trial_end),
    cancel_at_period_end: Boolean(subscription.cancel_at_period_end),
    updated_at: new Date().toISOString(),
  }, { onConflict: "user_id" });

  if (error) {
    // 500 so Stripe retries: the payment happened and the entitlement did
    // not, which is the one failure here worth being noisy and repeated about.
    console.error("stripe webhook: could not write subscription", error.message);
    return NextResponse.json({ error: "write failed" }, { status: 500 });
  }

  return NextResponse.json({ received: true, handled: true });
}

/**
 * Stripe only ever POSTs here. A browser GET therefore returns 405 with an
 * empty body, which renders as a blank white page and is indistinguishable
 * from a failed deployment to anyone checking the URL by hand — which is
 * exactly what someone does when setting this up.
 *
 * So it answers. It reveals nothing: whether this endpoint exists is already
 * public the moment it is registered with Stripe, and the signature check is
 * what protects it, not obscurity.
 */
export function GET() {
  return NextResponse.json({
    endpoint: "stripe webhook",
    accepts: "POST, signed by Stripe",
    configured: Boolean(PROJECT_URL && SERVICE_KEY && WEBHOOK_SECRET),
  });
}
