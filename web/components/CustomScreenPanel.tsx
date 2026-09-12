"use client";

import { useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { isRanked } from "@/lib/format";
import type { Bar, LearnFile, ParamSpec, ScreenFile, Setup } from "@/lib/types";
import { StockCard } from "./StockCard";
import { Tooltip } from "./Tooltip";

/**
 * The dial panel is generated from the detector param schema, so it can never
 * drift from the code that produced the lists.
 *
 * Two dials — the lookback window and the swing threshold — decide where the
 * base is before any metric exists, so they cannot be applied to an already
 * published setup. They are shown, disabled, with the reason, rather than
 * quietly dropped from a panel that claims to be generated from the schema.
 */
const NEEDS_RESCAN = new Set(["base_lookback_weeks", "swing_threshold_pct",
                              "fresh_breakout_sessions", "all_time_high_tolerance_pct",
                              "max_weeks_listed"]);

type Values = Record<string, number | boolean>;

export function CustomScreenPanel({
  learn, files, bars,
}: {
  learn: LearnFile[];
  files: ScreenFile[];
  bars: Record<string, Bar[]>;
}) {
  const { requireSignUp } = useAuth();
  const [screen, setScreen] = useState(learn[0]?.screen ?? "vcp");
  const spec = learn.find((l) => l.screen === screen) ?? learn[0];
  const file = files.find((f) => f.screen === screen);

  const [values, setValues] = useState<Values>(() => initial(spec?.params ?? []));

  const setups = useMemo(() => {
    const all: Setup[] = file ? Object.values(file.setups).flat() : [];
    return all.filter((setup) => passes(setup, values));
  }, [file, values]);

  if (!spec) return null;

  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        {learn.map((option) => (
          <button
            key={option.screen}
            type="button"
            className="control footnote"
            style={{ borderRadius: "var(--radius-pill)" }}
            aria-pressed={option.screen === screen}
            onClick={() => {
              setScreen(option.screen);
              setValues(initial(option.params));
            }}
          >
            {option.name}
          </button>
        ))}
      </div>

      <div className="stack">
        {spec.params.map((param) => {
          const locked = NEEDS_RESCAN.has(param.key);
          return (
            <div key={param.key} className="card stack" style={{ gap: "var(--gap-xs)" }}>
              <span className="row footnote" style={{ gap: "var(--gap-xs)" }}>
                <span className="grow muted">{param.label}</span>
                <Tooltip label={param.label} text={param.help} />
              </span>
              {param.kind === "boolean" ? (
                <div className="row" style={{ gap: 0 }}>
                  {[true, false].map((choice, index) => (
                    <button
                      key={String(choice)}
                      type="button"
                      className="control footnote"
                      disabled={locked}
                      aria-pressed={values[param.key] === choice}
                      style={{
                        borderRadius: index === 0 ? "var(--radius) 0 0 var(--radius)"
                          : "0 var(--radius) var(--radius) 0",
                        marginLeft: index ? -1 : 0,
                      }}
                      onClick={() => setValues({ ...values, [param.key]: choice })}
                    >
                      {choice ? "On" : "Off"}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="row" style={{ gap: "var(--gap-sm)" }}>
                  <input
                    type="range"
                    disabled={locked}
                    min={param.minimum ?? 0}
                    max={param.maximum ?? 100}
                    step={param.step ?? 1}
                    value={Number(values[param.key] ?? 0)}
                    onChange={(event) =>
                      setValues({ ...values, [param.key]: Number(event.target.value) })}
                    style={{ flex: 1, accentColor: "var(--brand)" }}
                    aria-label={param.label}
                  />
                  <span className="num" style={{ width: 62, textAlign: "right" }}>
                    {String(values[param.key])}{param.unit}
                  </span>
                </div>
              )}
              {locked && (
                <span className="caption dim">
                  Changing this one needs a fresh scan of the whole universe, so it is
                  fixed here at the published value.
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        <button type="button" className="control primary"
                onClick={() => requireSignUp("Save this screen")}>
          Save this screen
        </button>
        <button type="button" className="control"
                onClick={() => setValues(initial(spec.params))}>
          Reset to defaults
        </button>
      </div>

      <p className="footnote muted">
        {setups.length} of {file?.total ?? 0} published {spec.name} setups still pass
        with these dials.
      </p>

      <div className="grid-auto">
        {setups.map((setup) => (
          <StockCard key={setup.symbol} setup={setup} bars={bars[setup.symbol]} />
        ))}
      </div>
    </div>
  );
}

function initial(params: ParamSpec[]): Values {
  const out: Values = {};
  for (const param of params) {
    out[param.key] = param.value as number | boolean;
  }
  return out;
}

function passes(setup: Setup, values: Values): boolean {
  const rs = values.min_rs;
  if (typeof rs === "number") {
    if (!isRanked(setup.rs_rating) || setup.rs_rating < rs) return false;
  }
  if (values.require_above_50ma === true && (setup.price_vs_50ma_pct ?? -1) <= 0) return false;
  const from52 = values.max_from_52w_high_pct;
  if (typeof from52 === "number" && (setup.from_52w_high_pct ?? 0) > from52) return false;
  const minWeeks = values.min_base_weeks;
  if (typeof minWeeks === "number" && (setup.base_weeks ?? 0) < minWeeks) return false;
  const maxDepth = values.max_base_depth_pct;
  if (typeof maxDepth === "number" && (setup.base_depth_pct ?? 0) > maxDepth) return false;
  const fromPivot = values.max_from_pivot_pct;
  if (typeof fromPivot === "number" && (setup.now_vs_pivot_pct ?? 0) < -fromPivot) return false;
  const atr = values.max_second_half_atr_ratio;
  if (typeof atr === "number" && setup.tightening_atr_ratio) {
    if (1 / setup.tightening_atr_ratio > atr) return false;
  }
  const vol = values.max_second_half_volume_ratio;
  if (typeof vol === "number" && setup.volume_dryup_ratio) {
    if (1 / setup.volume_dryup_ratio > vol) return false;
  }
  return true;
}
