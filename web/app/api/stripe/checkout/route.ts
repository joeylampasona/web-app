import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

/**
 * Start a subscription: mint a Stripe Checkout Session for the caller.
 *
 * The caller is identified the same way as the gated route — by their own
 * access token, checked with Supabase — because the one thing that must not be
 * client-supplied is *who is buying*. Taking a user id from the request body
 * would let anyone start a subscription that lands on somebody else's account,
 * or worse, name an account they intend to take over later.
 *
 * The price is not client-supplied either. The body picks a plan by name and
 * this maps it to a configured id; accepting a price id from the browser means
 * accepting any price in the account, including a one-cent one.
 */
export const dynamic = "force-dynamic";

const PROJECT_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const STRIPE_KEY = process.env.STRIPE_SECRET_KEY;
const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://thetape.cc";

// Seven days. Set here rather than on the Price so it lives in one place and
// applies identically to both plans.
const TRIAL_DAYS = 7;

function priceFor(plan: string): string | null {
  if (plan === "monthly") return process.env.STRIPE_PRICE_ID_MONTHLY ?? null;
  if (plan === "annual") return process.env.STRIPE_PRICE_ID_ANNUAL ?? null;
  return null;
}

export async function POST(request: Request) {
  if (!PROJECT_URL || !ANON || !STRIPE_KEY) {
    return NextResponse.json({ error: "not configured" }, { status: 503 });
  }

  const authorization = request.headers.get("authorization") ?? "";
  if (!authorization.startsWith("Bearer ")) {
    return NextResponse.json({ error: "sign in first" }, { status: 401 });
  }

  // Ask Supabase who this token belongs to. Never trust the body for identity.
  const supabase = createClient(PROJECT_URL, ANON, {
    global: { headers: { Authorization: authorization } },
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data: { user }, error: whoError } = await supabase.auth.getUser();
  if (whoError || !user) {
    return NextResponse.json({ error: "sign in first" }, { status: 401 });
  }

  let plan = "monthly";
  try {
    const body = await request.json();
    if (typeof body?.plan === "string") plan = body.plan;
  } catch {
    // An absent or unparseable body means the default plan, not an error.
  }
  const price = priceFor(plan);
  if (!price) {
    return NextResponse.json({ error: "unknown plan" }, { status: 400 });
  }

  const form = new URLSearchParams({
    mode: "subscription",
    "line_items[0][price]": price,
    "line_items[0][quantity]": "1",
    success_url: `${SITE}/account?checkout=done`,
    cancel_url: `${SITE}/account?checkout=cancelled`,
    "subscription_data[trial_period_days]": String(TRIAL_DAYS),
    // Prefilled so the Stripe customer and the Supabase user share an address,
    // which is what makes a support enquiry answerable.
    customer_email: user.email ?? "",
    client_reference_id: user.id,
    "metadata[user_id]": user.id,
    // Also on the subscription itself, and this is the load-bearing one: a
    // customer.subscription.updated event months from now carries the
    // subscription's metadata, not the checkout session's. Without it, a
    // renewal or cancellation arrives with no way to tell whose it is.
    "subscription_data[metadata][user_id]": user.id,
  });

  const response = await fetch("https://api.stripe.com/v1/checkout/sessions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${STRIPE_KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: form,
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.url) {
    // Stripe's message can name the account or the price; it is not for the
    // browser. The server log keeps it.
    console.error("stripe checkout failed", response.status, payload?.error?.message);
    return NextResponse.json({ error: "could not start checkout" }, { status: 502 });
  }

  return NextResponse.json({ url: payload.url });
}
