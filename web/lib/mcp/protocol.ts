/**
 * The Model Context Protocol, as much of it as a read-only server needs.
 *
 * MCP is JSON-RPC 2.0 with a handful of agreed methods. A client says hello
 * (`initialize`), asks what the server can do (`tools/list`), and then asks it
 * to do one of those things (`tools/call`). That is the whole conversation a
 * server with only tools ever has, so this is written out by hand rather than
 * taken from the official SDK: the SDK's HTTP transport is built around
 * Node's request and response objects and a table of open sessions, and a
 * Next.js route handler on a serverless platform has neither. What is here is
 * the stateless half of the "streamable HTTP" transport: every request is a
 * POST that carries everything needed to answer it, and the answer is one
 * JSON body.
 *
 * Deliberately not here, and not advertised: resources, prompts, sampling,
 * logging, server-initiated messages, sessions. A client that asks for one
 * gets JSON-RPC's "method not found", which is the protocol's own way of
 * saying so.
 *
 * Nothing in this file knows what the tools are or where their data lives.
 * It can be read, and tested, as a protocol and nothing else.
 */

/** The protocol revisions this server will speak, newest first.
 *
 *  The client names the revision it wants in `initialize`. If it is one of
 *  these it is echoed back; if not, the newest one here is offered and the
 *  client decides whether it can live with that, which is what the
 *  specification says a server should do. The three differ in ways that do
 *  not touch a tools-only server, with one exception handled below: batches
 *  of requests in one body existed in 2025-03-26 and were removed in
 *  2025-06-18. */
export const PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"] as const;
export const LATEST_PROTOCOL = PROTOCOL_VERSIONS[0];

export const PARSE_ERROR = -32700;
export const INVALID_REQUEST = -32600;
export const METHOD_NOT_FOUND = -32601;
export const INVALID_PARAMS = -32602;
export const INTERNAL_ERROR = -32603;

type Id = string | number | null;

/** The subset of JSON Schema the tools' inputs are written in, and the only
 *  subset `problems` below understands. Kept this small on purpose: a schema
 *  the server publishes and then does not enforce is worse than none. */
export interface InputSchema {
  type: "object";
  properties: Record<string, {
    type: "string" | "integer" | "boolean";
    description: string;
    enum?: string[];
    pattern?: string;
    maxLength?: number;
    minimum?: number;
    maximum?: number;
  }>;
  required?: string[];
  additionalProperties: false;
}

export interface ToolResult {
  content: { type: "text"; text: string }[];
  isError?: boolean;
}

export interface Tool {
  name: string;
  /** A short name a person would read in a client's list of tools. */
  title: string;
  /** Written for the model that will decide whether to call it. */
  description: string;
  inputSchema: InputSchema;
  run: (args: Record<string, unknown>) => Promise<ToolResult> | ToolResult;
}

export interface Server {
  name: string;
  title: string;
  version: string;
  /** Read by the client's model before it uses any tool. */
  instructions: string;
  tools: Tool[];
}

export function failed(message: string): ToolResult {
  return { content: [{ type: "text", text: message }], isError: true };
}

/** What is wrong with a tool's arguments, in a sentence a model can act on,
 *  or null when nothing is. */
export function problems(schema: InputSchema, args: Record<string, unknown>): string | null {
  for (const key of Object.keys(args)) {
    if (!(key in schema.properties)) {
      const known = Object.keys(schema.properties);
      return `Unknown argument "${key}". This tool takes ${
        known.length ? known.map((k) => `"${k}"`).join(", ") : "no arguments"}.`;
    }
  }
  for (const key of schema.required ?? []) {
    if (args[key] === undefined || args[key] === null) return `Missing required argument "${key}".`;
  }
  for (const [key, rule] of Object.entries(schema.properties)) {
    const value = args[key];
    if (value === undefined || value === null) continue;
    if (rule.type === "string") {
      if (typeof value !== "string") return `"${key}" must be a string.`;
      if (rule.maxLength !== undefined && value.length > rule.maxLength) {
        return `"${key}" is longer than ${rule.maxLength} characters.`;
      }
      if (rule.enum && !rule.enum.includes(value)) {
        return `"${key}" must be one of: ${rule.enum.join(", ")}.`;
      }
      if (rule.pattern && !new RegExp(rule.pattern).test(value)) {
        return `"${key}" is not in the expected form. ${rule.description}`;
      }
    } else if (rule.type === "integer") {
      if (typeof value !== "number" || !Number.isInteger(value)) return `"${key}" must be a whole number.`;
      if (rule.minimum !== undefined && value < rule.minimum) return `"${key}" must be at least ${rule.minimum}.`;
      if (rule.maximum !== undefined && value > rule.maximum) return `"${key}" must be at most ${rule.maximum}.`;
    } else if (rule.type === "boolean") {
      if (typeof value !== "boolean") return `"${key}" must be true or false.`;
    }
  }
  return null;
}

function reply(id: Id, result: unknown) {
  return { jsonrpc: "2.0" as const, id, result };
}

function refuse(id: Id, code: number, message: string) {
  return { jsonrpc: "2.0" as const, id, error: { code, message } };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Answer one JSON-RPC message. Null when the message wants no answer: a
 *  notification, or a response the client is sending us, which a server that
 *  never asks the client anything has no use for. */
export async function answer(server: Server, message: unknown): Promise<object | null> {
  if (!isObject(message) || message.jsonrpc !== "2.0") {
    return refuse(null, INVALID_REQUEST, "Not a JSON-RPC 2.0 message.");
  }
  const hasId = "id" in message;
  const id = (hasId ? message.id : null) as Id;
  if (hasId && id !== null && typeof id !== "string" && typeof id !== "number") {
    return refuse(null, INVALID_REQUEST, "The id must be a string or a number.");
  }
  if (typeof message.method !== "string") {
    // A response or an error addressed to us. Nothing was asked, so nothing
    // is owed; it is accepted and dropped.
    if ("result" in message || "error" in message) return null;
    return refuse(id, INVALID_REQUEST, "The message has no method.");
  }
  const method = message.method;
  // Every notification is accepted without an answer, the ones we know
  // (initialized, cancelled) and the ones we do not: JSON-RPC forbids
  // replying to a notification at all.
  if (!hasId) return null;

  const params = message.params === undefined ? {} : message.params;
  if (!isObject(params)) return refuse(id, INVALID_PARAMS, "params must be an object.");

  switch (method) {
    case "initialize": {
      const asked = typeof params.protocolVersion === "string" ? params.protocolVersion : "";
      const version = (PROTOCOL_VERSIONS as readonly string[]).includes(asked) ? asked : LATEST_PROTOCOL;
      return reply(id, {
        protocolVersion: version,
        // Tools, and the list of them never changes while a client is
        // connected. Nothing else is offered.
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: server.name, title: server.title, version: server.version },
        instructions: server.instructions,
      });
    }
    case "ping":
      return reply(id, {});
    case "tools/list":
      return reply(id, {
        tools: server.tools.map((tool) => ({
          name: tool.name,
          title: tool.title,
          description: tool.description,
          inputSchema: tool.inputSchema,
          // Hints, not guarantees, but true ones: every tool reads a fixed
          // set of published files and changes nothing anywhere.
          annotations: { title: tool.title, readOnlyHint: true, destructiveHint: false,
                         idempotentHint: true, openWorldHint: false },
        })),
      });
    case "tools/call": {
      const tool = server.tools.find((t) => t.name === params.name);
      if (typeof params.name !== "string" || !tool) {
        return refuse(id, INVALID_PARAMS, `Unknown tool: ${String(params.name)}`);
      }
      const args = params.arguments === undefined ? {} : params.arguments;
      if (!isObject(args)) return refuse(id, INVALID_PARAMS, "arguments must be an object.");
      // A bad argument is the model's mistake to correct, so it comes back
      // as a tool result it can read, not as a protocol error its client
      // may swallow.
      const wrong = problems(tool.inputSchema, args);
      if (wrong) return reply(id, failed(wrong));
      try {
        return reply(id, await tool.run(args));
      } catch {
        return reply(id, failed("The Tape could not read that just now. Nothing was changed; try again."));
      }
    }
    default:
      return refuse(id, METHOD_NOT_FOUND, `Method not found: ${method}`);
  }
}

export interface Outcome {
  status: number;
  /** Absent when the status carries the whole answer. */
  body?: object;
}

/** Answer a POST body.
 *
 *  One message, or an array of them. Arrays were part of the protocol in the
 *  2025-03-26 revision and dropped from the next; a stateless server cannot
 *  know which revision a given caller negotiated, and answering a batch is
 *  harmless, so batches are answered rather than refused. An array of only
 *  notifications gets 202 and no body, the same as a single one. */
export async function respond(server: Server, raw: string, maxBatch = 20): Promise<Outcome> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { status: 400, body: refuse(null, PARSE_ERROR, "The body is not valid JSON.") };
  }
  if (Array.isArray(parsed)) {
    if (parsed.length === 0) {
      return { status: 400, body: refuse(null, INVALID_REQUEST, "An empty batch.") };
    }
    if (parsed.length > maxBatch) {
      return { status: 400, body: refuse(null, INVALID_REQUEST, `At most ${maxBatch} messages in one batch.`) };
    }
    const answers = (await Promise.all(parsed.map((message) => answer(server, message))))
      .filter((a): a is object => a !== null);
    return answers.length ? { status: 200, body: answers } : { status: 202 };
  }
  const single = await answer(server, parsed);
  return single ? { status: 200, body: single } : { status: 202 };
}
