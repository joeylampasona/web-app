import { NextResponse } from "next/server";
import { PROTOCOL_VERSIONS, respond } from "@/lib/mcp/protocol";
import { SERVER } from "@/lib/mcp/tools";

/**
 * The Tape, for a reader's own AI.
 *
 *     claude mcp add --transport http the-tape https://thetape.cc/api/mcp
 *
 * An MCP server over HTTP: a client POSTs JSON-RPC here and gets JSON back.
 * It is stateless. There is no session, no stream held open, nothing kept
 * between one request and the next, which is the only shape that suits a
 * route on a serverless platform and is all a server with seven read-only
 * tools needs. The protocol is in lib/mcp/protocol.ts and the tools in
 * lib/mcp/tools.ts; this file is only the door.
 *
 * It has no lock on it, on purpose and for now. Everything behind it is what
 * a signed-out visitor to the site can already read, served through the same
 * loaders the public pages use, so there is nothing to protect but the
 * machine. That is what the limits below are for: a ceiling on the size of a
 * request, a ceiling on requests a minute from one address, and answers that
 * are never cached by anything in between.
 *
 * A subscriber's version, with the full lists, would need to know who is
 * asking. A browser session does not travel with an AI client, so that means
 * a token a subscriber can copy from their settings and a table to hold it.
 * Until that exists this serves the public half and says so.
 */
export const dynamic = "force-dynamic";
export const revalidate = 0;

/** No message a client sends this server is long. */
const MAX_BODY = 64 * 1024;

/** Requests a minute from one address, per server instance. On a serverless
 *  platform there may be several instances and each keeps its own count, so
 *  this is a brake on one runaway loop, not a quota. */
const PER_MINUTE = 120;
const WINDOW_MS = 60_000;
const seen = new Map<string, { count: number; resets: number }>();

function overLimit(address: string, now: number): number | null {
  if (seen.size > 5000) {
    for (const [key, entry] of seen) if (entry.resets <= now) seen.delete(key);
  }
  const entry = seen.get(address);
  if (!entry || entry.resets <= now) {
    seen.set(address, { count: 1, resets: now + WINDOW_MS });
    return null;
  }
  entry.count += 1;
  return entry.count > PER_MINUTE ? Math.ceil((entry.resets - now) / 1000) : null;
}

/** Any origin may call. The specification asks a server to check the Origin
 *  header so that a web page cannot reach an MCP server running on the
 *  reader's own machine; this one runs on the public internet, holds no
 *  credentials and serves only public data, so there is nothing an origin
 *  could borrow. Browser-based clients need the headers to connect at all. */
const CORS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Accept, Authorization, MCP-Protocol-Version, Mcp-Session-Id, Last-Event-ID",
  "Access-Control-Max-Age": "86400",
};

const BASE: Record<string, string> = { ...CORS, "Cache-Control": "no-store" };

function rpcError(status: number, code: number, message: string, extra: Record<string, string> = {}) {
  return NextResponse.json({ jsonrpc: "2.0", id: null, error: { code, message } },
                           { status, headers: { ...BASE, ...extra } });
}

export async function POST(request: Request) {
  const address = (request.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "unknown";
  const wait = overLimit(address, Date.now());
  if (wait !== null) {
    return rpcError(429, -32000, `Too many requests. Try again in ${wait} seconds.`,
                    { "Retry-After": String(wait) });
  }

  // After `initialize`, a client on the 2025-06-18 revision names the
  // revision it negotiated on every request. One this server does not speak
  // is refused, as the specification requires; a request without the header
  // is taken as it comes, which is what older clients send.
  const named = request.headers.get("mcp-protocol-version");
  if (named && !(PROTOCOL_VERSIONS as readonly string[]).includes(named)) {
    return rpcError(400, -32600,
                    `Unsupported MCP-Protocol-Version "${named.slice(0, 40)}". `
                    + `This server speaks ${PROTOCOL_VERSIONS.join(", ")}.`);
  }

  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_BODY) return rpcError(413, -32600, "The request is too large.");
  const raw = await request.text();
  if (raw.length > MAX_BODY) return rpcError(413, -32600, "The request is too large.");

  const outcome = await respond(SERVER, raw);
  if (!outcome.body) return new NextResponse(null, { status: outcome.status, headers: BASE });
  return NextResponse.json(outcome.body, { status: outcome.status, headers: BASE });
}

/** A client may GET to open a stream for messages the server starts. This
 *  server never starts one, and the specification's answer for that is 405. */
export function GET() {
  return rpcError(405, -32000,
                  "This endpoint answers POSTed JSON-RPC only. See /mcp for how to connect.",
                  { Allow: "POST, OPTIONS" });
}

/** There is no session to end. */
export function DELETE() {
  return rpcError(405, -32000, "This server keeps no sessions.", { Allow: "POST, OPTIONS" });
}

export function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}
