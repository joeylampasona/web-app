import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const run = promisify(execFile);
const ROOT = path.resolve(process.cwd(), "..");

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
    const { stdout } = await run(process.env.PYTHON_BIN || "python3", args, {
      cwd: ROOT,
      maxBuffer: 64 * 1024 * 1024,
      timeout: 110_000,
    });
    return NextResponse.json(JSON.parse(stdout));
  } catch (error) {
    return NextResponse.json(
      {
        error:
          "The backtest engine did not run. Custom runs shell out to the Python " +
          "pipeline, so this route needs Python and the out/ tree on the same host. " +
          "The precomputed default for each screen is served without it.",
        detail: error instanceof Error ? error.message.slice(0, 400) : String(error),
      },
      { status: 503 },
    );
  }
}
