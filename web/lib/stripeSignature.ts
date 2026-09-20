import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Verify Stripe's webhook signature.
 *
 * This is the only thing standing between "Stripe says this person paid" and
 * "anyone who can POST to a public URL says this person paid". Nothing else in
 * the subscription flow re-checks it: the webhook is what writes entitlement,
 * with the service-role key, bypassing every policy.
 *
 * Written against the documented scheme rather than pulled in as a package, so
 * that it can be exercised here against forged and replayed inputs — which is
 * better assurance than an untested import.
 *
 * The header looks like:
 *     t=1699999999,v1=5257a869e7...,v0=...
 * and the signed payload is the timestamp, a full stop, and the RAW body. Raw
 * matters: parsing to an object and re-serialising changes the bytes and the
 * signature will not match.
 */

/** How far out of date a signature may be. Stripe's own guidance is five
 *  minutes. Without this, a signature captured once is valid forever, and a
 *  replayed "subscription created" is a free subscription. */
export const TOLERANCE_SECONDS = 300;

export type VerifyResult =
  | { ok: true }
  | { ok: false; reason: string };

function parseHeader(header: string): { timestamp: number; signatures: string[] } | null {
  let timestamp: number | null = null;
  const signatures: string[] = [];
  for (const part of header.split(",")) {
    const index = part.indexOf("=");
    if (index < 0) continue;
    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();
    if (key === "t") {
      const parsed = Number(value);
      // A non-numeric or negative timestamp is malformed, not merely old.
      if (!Number.isFinite(parsed) || parsed <= 0) return null;
      timestamp = parsed;
    } else if (key === "v1") {
      signatures.push(value);
    }
  }
  if (timestamp === null || signatures.length === 0) return null;
  return { timestamp, signatures };
}

/** Constant time, and false rather than throwing on a length mismatch —
 *  timingSafeEqual requires equal lengths and a thrown error would itself be
 *  a timing signal. */
function sameSignature(a: string, b: string): boolean {
  const left = Buffer.from(a, "utf8");
  const right = Buffer.from(b, "utf8");
  if (left.length !== right.length) return false;
  return timingSafeEqual(left, right);
}

export function verifyStripeSignature(
  rawBody: string,
  header: string | null,
  secret: string,
  nowSeconds: number = Math.floor(Date.now() / 1000),
  toleranceSeconds: number = TOLERANCE_SECONDS,
): VerifyResult {
  if (!secret) return { ok: false, reason: "no signing secret configured" };
  if (!header) return { ok: false, reason: "no signature header" };

  const parsed = parseHeader(header);
  if (!parsed) return { ok: false, reason: "malformed signature header" };

  // Both directions. A timestamp far in the future is as much a forgery as one
  // far in the past, and allowing it would make the replay window unbounded.
  const age = Math.abs(nowSeconds - parsed.timestamp);
  if (age > toleranceSeconds) {
    return { ok: false, reason: `timestamp outside tolerance (${age}s)` };
  }

  const expected = createHmac("sha256", secret)
    .update(`${parsed.timestamp}.${rawBody}`, "utf8")
    .digest("hex");

  // Stripe may send several v1 signatures during a secret rotation; any one
  // matching is a pass. Every candidate is compared, without an early exit, so
  // the work does not depend on which one matches.
  let matched = false;
  for (const candidate of parsed.signatures) {
    if (sameSignature(candidate, expected)) matched = true;
  }
  return matched ? { ok: true } : { ok: false, reason: "signature mismatch" };
}
