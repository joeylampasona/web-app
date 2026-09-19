import type { BreadthCard, RegimeStatus } from "./types";

/**
 * One sentence on whether the tape is worth trading breakouts into.
 *
 * The home page needs a headline that means something, and the honest way to
 * get one is to say out loud which numbers it is built from and let the reader
 * check them. So this returns its evidence alongside its verdict, and the page
 * prints both. A verdict with no visible arithmetic behind it is a horoscope.
 *
 * Three tests, each worth -1, 0 or +1:
 *
 *   1. Breakouts against failed pokes. The sharpest of the three, because it is
 *      about this exact strategy rather than the market in general: when more
 *      names poke through a pivot and fall back than clear it and hold, the
 *      tape is charging you for entries it is not paying for.
 *   2. How much of the universe is above its 50-day line — participation.
 *   3. How much of it is in a confirmed uptrend — trend quality.
 *
 * The thresholds are deliberately wide, so most days come out "mixed". That is
 * the correct answer most of the time, and a read that swings between extremes
 * daily would be noise wearing a verdict's clothes.
 *
 * Missing cards are not treated as zeros. A test whose input is absent is
 * skipped and said to be skipped, and if fewer than two survive there is no
 * verdict at all — the page then says it cannot tell, which is a real answer.
 */

export type Verdict = "in_gear" | "mixed" | "against" | "unknown";

/** How many tests exist when every input is present: the regime plus the three
 *  breadth checks. Exported so nothing downstream has to hard-code the count
 *  and go stale the next time a test is added. */
export const TOTAL_TESTS = 4;

/**
 * The bar is deliberately higher for blessing than for warning.
 *
 * Getting "in gear" wrong costs money; getting "against" wrong costs a missed
 * trade. Those are not the same mistake, so they do not get the same threshold.
 *
 * The asymmetry also survives a test dropping out. With all four present,
 * blessing needs a clear majority while two negatives are enough to warn. This
 * caught a real miscalibration: the bar was 2 when there were three tests, and
 * adding a fourth left 2 in place -- which had quietly turned a majority into
 * a coin flip, and read an ordinary mixed day as in gear.
 */
const BLESS_AT = 3;
const WARN_AT = 2;

export interface ReadTest {
  label: string;
  detail: string;
  score: -1 | 0 | 1;
}

export interface MarketRead {
  verdict: Verdict;
  headline: string;
  blurb: string;
  tests: ReadTest[];
  /** How many of the TOTAL_TESTS had the data they needed. */
  measured: number;
}

function card(cards: BreadthCard[], key: string): BreadthCard | undefined {
  return cards.find((c) => c.key === key);
}

function pct(value: number): string {
  return `${value.toFixed(0)}%`;
}

export function readMarket(
  cards: BreadthCard[] | null | undefined,
  regime?: RegimeStatus | null,
): MarketRead {
  const all = cards ?? [];
  const tests: ReadTest[] = [];

  // `above: null` means the history is too short to know, which is not the
  // same as false. An unknown regime is skipped, never scored as a negative.
  if (regime && regime.above !== null) {
    tests.push({
      label: `${regime.symbol} against its 200-day line`,
      detail: regime.note,
      score: regime.above ? 1 : -1,
    });
  }

  const breakouts = card(all, "breakouts");
  const failed = card(all, "failed_pokes");
  // Nothing cleared a pivot and nothing failed at one. That is a holiday or a
  // gap in the data, not a hostile tape, and scoring it as hostile is wrong in
  // the direction that matters: it would tell someone to stand aside on the
  // strength of no evidence at all. 0 >= 0 * 1.5 is true, so this has to be
  // caught before the comparison rather than inside it.
  if (breakouts && failed && (breakouts.value > 0 || failed.value > 0)) {
    const b = breakouts.value;
    const f = failed.value;
    // 1.5x rather than a bare majority: pokes outnumber clean breakouts on
    // plenty of perfectly ordinary days, and a test that fires on every one of
    // them tells you nothing.
    const score: -1 | 0 | 1 = f >= b * 1.5 ? -1 : b >= f ? 1 : 0;
    tests.push({
      label: "Breakouts against failed pokes",
      detail: `${b.toFixed(0)} cleared a pivot, ${f.toFixed(0)} tested one and fell back.`,
      score,
    });
  }

  const above50 = card(all, "above_50ma");
  if (above50) {
    const v = above50.value;
    const score: -1 | 0 | 1 = v >= 55 ? 1 : v <= 40 ? -1 : 0;
    tests.push({
      label: "Above the 50-day line",
      detail: `${pct(v)} of the universe.`,
      score,
    });
  }

  const uptrend = card(all, "confirmed_uptrend");
  if (uptrend) {
    const v = uptrend.value;
    const score: -1 | 0 | 1 = v >= 40 ? 1 : v <= 25 ? -1 : 0;
    tests.push({
      label: "In a confirmed uptrend",
      detail: `${pct(v)} of the universe.`,
      score,
    });
  }

  const measured = tests.length;
  if (measured < 2) {
    return {
      verdict: "unknown",
      headline: "Not enough breadth data to call it",
      blurb:
        measured === 0
          ? "No breadth or index numbers were published in the last run, so there is nothing to read."
          : `Only one of the ${TOTAL_TESTS} checks had data, which is not enough to say anything.`,
      tests,
      measured,
    };
  }

  const total = tests.reduce((sum, t) => sum + t.score, 0);
  const belowTrend = regime?.above === false;
  if (total >= BLESS_AT && !belowTrend) {
    return {
      verdict: "in_gear",
      headline: "The tape is in gear",
      blurb:
        "Breakouts are being paid for and most of the market is participating. " +
        "This is the backdrop these screens are built for.",
      tests, measured,
    };
  }
  if (total <= -WARN_AT) {
    return {
      verdict: "against",
      headline: "The tape is against breakouts",
      blurb:
        "More names are failing at their pivots than holding above them, and " +
        "participation is thin. Bases that look clean still tend to fail in this.",
      tests, measured,
    };
  }
  if (belowTrend && total >= 2) {
    return {
      verdict: "mixed",
      headline: "Mixed, under a falling benchmark",
      blurb:
        `Breadth is holding up, but ${regime?.symbol ?? "the benchmark"} is below ` +
        "its 200-day line. Breadth can look healthy for a week inside a downtrend, " +
        "and those are the weeks that cost the most, because everything else is " +
        "telling you to buy.",
      tests, measured,
    };
  }
  return {
    verdict: "mixed",
    headline: "Mixed",
    blurb:
      "Some of the market is working and some of it is not. Breakouts go both " +
      "ways in this, so the individual setup matters more than usual.",
    tests, measured,
  };
}
