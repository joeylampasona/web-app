import "server-only";
import type { Settings } from "./backtestKey";

/**
 * Running a custom backtest where there is no Python.
 *
 * The engine re-detects every setup historically, so it needs the whole price
 * database — not the 180 bars a stock ships with. Porting it to run in this
 * process would mean a second implementation of the numbers the whole site is
 * built on, free to disagree with the first. So the real engine runs where the
 * database already lives: a GitHub Actions workflow, which publishes the answer
 * to the `backtests` branch, and the site reads it from there.
 *
 * Reading needs no credential — the repository is public. Only starting a run
 * does, and that token is server-side only and never reaches the browser.
 */
const REPO = process.env.GITHUB_REPO ?? "joeylampasona/web-app";
const TOKEN = process.env.GITHUB_DISPATCH_TOKEN ?? "";
const WORKFLOW = "backtest.yml";
const REF = process.env.GITHUB_DEFAULT_BRANCH ?? "main";

export const canDispatch = Boolean(TOKEN);

/** A published result for these settings and this session, if one exists. */
export async function fetchResult(asOf: string, key: string): Promise<unknown | null> {
  const url = `https://raw.githubusercontent.com/${REPO}/backtests/${asOf}/${key}.json`;
  const response = await fetch(url, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Reading the result failed: HTTP ${response.status}`);
  }
  return (await response.json()) as unknown;
}

/** Ask the workflow to compute one. Resolves once GitHub has accepted the job. */
export async function dispatch(settings: Settings, key: string): Promise<void> {
  const url = `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ref: REF,
      // Workflow inputs are strings. The workflow passes them straight to the
      // CLI, which validates them again on the far side.
      inputs: {
        key,
        screen: settings.screen,
        enter: settings.enter,
        exit_rule: settings.exit_rule,
        positions: String(settings.positions),
        stop_pct: String(settings.stop_pct),
        risk_pct: String(settings.risk_pct),
        period: settings.period,
        starting_capital: String(settings.starting_capital),
        skip_weak_markets: String(settings.skip_weak_markets),
        skip_earnings_7d: String(settings.skip_earnings_7d),
      },
    }),
  });
  if (response.status === 204) return;

  const detail = (await response.text()).slice(0, 300);
  if (response.status === 401 || response.status === 403) {
    throw new Error(
      "GitHub refused the request to start a run. The token needs the Actions " +
      "permission on this repository, and it expires — check it has not.",
    );
  }
  if (response.status === 404) {
    throw new Error(
      `GitHub has no workflow ${WORKFLOW} on ${REF} of ${REPO}, or the token ` +
      "cannot see it. A workflow only accepts runs once it exists on the " +
      "default branch.",
    );
  }
  throw new Error(`GitHub returned HTTP ${response.status} starting the run. ${detail}`);
}
