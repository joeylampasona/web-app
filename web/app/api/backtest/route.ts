import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const run = promisify(execFile);
const ROOT = path.resolve(process.cwd(), "..");

/** The project's dependencies live in a virtual environment, so a bare
 *  `python3` finds the system interpreter and fails on the first import.
 *  Prefer the venv, which is where `pip install -r requirements.txt` put them. */
function pythonBin(): string {
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN;
  for (const candidate of [
    path.join(ROOT, ".venv", "bin", "python"),
    path.join(ROOT, "venv", "bin", "python"),
  ]) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return "python3";
}

// Everything the engine accepts, allow-listed. Nothing reaches a shell: the
// arguments go to execFile as an array, and any value outside these sets is
// rejected before we get there.
const SCREENS = ["vcp", "blue_sky", "multi_year", "ipo"];
const ENTER = ["breakout_close", "at_pivot"];
const POSITIONS = [3, 5, 8, 10];
const STOPS = [7, 8, 10];
const EXITS = ["trail_50d", "trail_30w", "take_25"];
const RISKS = [1, 1.5, 2];

export async function POST(request: Request) {
  let payload: Record<string, unknown>;
  try {
    payload = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "bad request body" }, { status: 400 });
  }

  const screen = String(payload.screen ?? "vcp");
  const enter = String(payload.enter ?? "breakout_close");
  const exitRule = String(payload.exit_rule ?? "trail_50d");
  const positions = Number(payload.positions ?? 5);
  const stop = Number(payload.stop_pct ?? 8);
  const risk = Number(payload.risk_pct ?? 1.5);
  const capital = Number(payload.starting_capital ?? 100000);
  const period = String(payload.period ?? "all");

  const invalid =
    !SCREENS.includes(screen) ||
    !ENTER.includes(enter) ||
    !EXITS.includes(exitRule) ||
    !POSITIONS.includes(positions) ||
    !STOPS.includes(stop) ||
    !RISKS.includes(risk) ||
    !Number.isFinite(capital) || capital < 1000 || capital > 100_000_000 ||
    !(period === "all" || /^\d{4}$/.test(period));

  if (invalid) {
    return NextResponse.json({ error: "one of those settings is not allowed" },
                             { status: 400 });
  }

  const args = [
    "-m", "cli", "backtest", "--json",
    "--screen", screen,
    "--enter", enter,
    "--positions", String(positions),
    "--stop", String(stop),
    "--exit-rule", exitRule,
    "--risk", String(risk),
    "--capital", String(capital),
    "--period", period,
    payload.skip_weak_markets === false ? "--no-skip-weak-markets" : "--skip-weak-markets",
    payload.skip_earnings_7d === false ? "--no-skip-earnings" : "--skip-earnings",
  ];

  try {
    const { stdout } = await run(pythonBin(), args, {
      cwd: ROOT,
      maxBuffer: 64 * 1024 * 1024,
      timeout: 110_000,
    });
    return NextResponse.json(JSON.parse(stdout));
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    const missingModule = /No module named '([^']+)'/.exec(detail);
    const notFound = /ENOENT|not found/i.test(detail);

    // Say which of the three things actually went wrong, rather than offering
    // one generic explanation that is only sometimes the right one.
    let reason: string;
    if (missingModule) {
      reason =
        `The Python it used is missing ${missingModule[1]}. Install the ` +
        `dependencies into the environment this server can see: ` +
        `pip install -r requirements.txt, or set PYTHON_BIN to the interpreter ` +
        `that has them.`;
    } else if (notFound) {
      reason =
        `No Python interpreter was found at ${pythonBin()}. On a host without ` +
        `Python — Vercel, for one — custom runs are not available, and the ` +
        `precomputed default for each screen is served instead.`;
    } else {
      reason =
        "The engine started but did not finish. The precomputed default for " +
        "each screen is still served.";
    }

    return NextResponse.json(
      { error: `The backtest engine did not run. ${reason}`,
        python: pythonBin(),
        detail: detail.slice(0, 400) },
      { status: 503 },
    );
  }
}
