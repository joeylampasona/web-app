import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";
import { parseSettings, resultKey, sameSettings, type Settings } from "@/lib/backtestKey";
import { canDispatch, dispatch, fetchResult } from "@/lib/backtestRemote";
import { getBacktestPreset, getBacktestPresetIndex } from "@/lib/data";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const run = promisify(execFile);
const ROOT = path.resolve(process.cwd(), "..");

/** The project's dependencies live in a virtual environment, so a bare
 *  `python3` finds the system interpreter and fails on the first import.
 *  Prefer the venv, which is where `pip install -r requirements.txt` put them. */
function pythonBin(): string | null {
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN;
  for (const candidate of [
    path.join(ROOT, ".venv", "bin", "python"),
    path.join(ROOT, "venv", "bin", "python"),
  ]) {
    if (fs.existsSync(candidate)) return candidate;
  }
  // Only a local checkout has the engine and the database beside it. On a host
  // that has neither, there is nothing for an interpreter to run.
  return fs.existsSync(path.join(ROOT, "cli", "__main__.py")) &&
         fs.existsSync(path.join(ROOT, "var")) ? "python3" : null;
}

export async function POST(request: Request) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "bad request body" }, { status: 400 });
  }

  const parsed = parseSettings(body);
  if (!parsed.ok) {
    return NextResponse.json({ error: parsed.error }, { status: 400 });
  }
  const settings = parsed.settings;

  // 1. Already computed tonight? Presets cover the four defaults; the branch
  //    covers everything anyone has asked for since this session's data landed.
  const cached = await lookup(settings);
  if (cached) return NextResponse.json(cached);

  // 2. A local checkout has the engine and the database. Run it directly —
  //    ten seconds beats two minutes, and it works with no network at all.
  const python = pythonBin();
  if (python) return runLocally(python, settings);

  // 3. Otherwise ask the workflow that does have them.
  if (!canDispatch) {
    return NextResponse.json(
      { error: "Custom runs are not switched on for this deploy. The four " +
               "default backtests, one per screen, are precomputed and still " +
               "available." },
      { status: 503 },
    );
  }
  const key = resultKey(settings);
  try {
    await dispatch(settings, key);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 503 },
    );
  }
  return NextResponse.json({
    status: "queued",
    key,
    note: "Running this on years of prices takes a couple of minutes.",
  });
}

/** A preset or a previously published result for this session's data. */
async function lookup(settings: Settings): Promise<unknown | null> {
  const index = getBacktestPresetIndex();
  if (!index?.as_of) return null;

  for (const [hash, preset] of Object.entries(index.presets ?? {})) {
    if (sameSettings(settings, preset)) {
      const preloaded = getBacktestPreset(hash);
      if (preloaded) return preloaded;
    }
  }
  try {
    return await fetchResult(index.as_of, resultKey(settings));
  } catch {
    // A cache miss must never fail the request — it only means we compute it.
    return null;
  }
}

async function runLocally(python: string, settings: Settings) {
  const args = [
    "-m", "cli", "backtest", "--json",
    "--screen", settings.screen,
    "--enter", settings.enter,
    "--positions", String(settings.positions),
    "--stop", String(settings.stop_pct),
    "--exit-rule", settings.exit_rule,
    "--risk", String(settings.risk_pct),
    "--capital", String(settings.starting_capital),
    "--period", settings.period,
    settings.skip_weak_markets ? "--skip-weak-markets" : "--no-skip-weak-markets",
    settings.skip_earnings_7d ? "--skip-earnings" : "--no-skip-earnings",
  ];
  try {
    const { stdout } = await run(python, args, {
      cwd: ROOT, maxBuffer: 64 * 1024 * 1024, timeout: 110_000,
    });
    return NextResponse.json(JSON.parse(stdout));
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    const missingModule = /No module named '([^']+)'/.exec(detail);

    // Say which of the three things actually went wrong, rather than offering
    // one generic explanation that is only sometimes the right one.
    let reason: string;
    if (missingModule) {
      reason =
        `The Python it used is missing ${missingModule[1]}. Install the ` +
        `dependencies into the environment this server can see: ` +
        `pip install -r requirements.txt, or set PYTHON_BIN to the interpreter ` +
        `that has them.`;
    } else if (/ENOENT|not found/i.test(detail)) {
      reason = `No Python interpreter was found at ${python}.`;
    } else if (/timed out|ETIMEDOUT/i.test(detail)) {
      reason = "The engine ran past its time limit. A narrower period finishes faster.";
    } else {
      reason = "The engine started but did not finish.";
    }
    return NextResponse.json(
      { error: `The backtest engine did not run. ${reason}`, python, detail: detail.slice(0, 400) },
      { status: 503 },
    );
  }
}
