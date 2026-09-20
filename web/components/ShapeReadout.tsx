import { price, ratio } from "@/lib/format";
import type { ShapeGeometry } from "@/lib/types";

/**
 * The fitted geometry behind a shape screen.
 *
 * All of this was already being published and none of it was being drawn: the
 * shape screens showed the same card as a base screen, so a falling wedge and
 * a flat base looked identical on the page that was supposed to tell them
 * apart. These are the numbers that make the shape a shape.
 *
 * Nulls are load-bearing here and are shown as absences with a reason, not as
 * dashes. A flag has no apex because two parallel lines never meet; a squeeze
 * has no target because a volatility state projects no measured move. Printing
 * "—" for both would make them look like data that failed to arrive.
 */
function Row({ label, value, help }: { label: string; value: string; help?: string }) {
  return (
    <div className="metric-row">
      <span className="label">{label}{help && <span className="dim"> · {help}</span>}</span>
      <span className="value">{value}</span>
    </div>
  );
}

export function ShapeReadout({ shape }: { shape: ShapeGeometry | null | undefined }) {
  if (!shape) return null;
  const isFlag = shape.kind.endsWith("flag");
  const isSqueeze = shape.kind === "squeeze";

  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      {shape.stale && (
        <p className="footnote" style={{ margin: 0, color: "var(--warn)" }}>
          The lines have nearly met. There is little room left inside the shape,
          which is usually where they stop resolving cleanly and start drifting
          out sideways.
        </p>
      )}

      <div>
        <Row label="Level" value={price(shape.level)}
             help={shape.direction === "short" ? "floor" : "ceiling"} />
        {/* A short shape is wrong when price goes UP through its stop. Calling
            that "wrong below" reverses the only thing the row is there to say. */}
        {shape.stop !== null && (
          <Row label={shape.direction === "short" ? "Wrong above" : "Wrong below"}
               value={price(shape.stop)} />
        )}

        {isSqueeze ? (
          <Row
            label="Measured target"
            value="none"
            help="a squeeze has no height to project"
          />
        ) : shape.target !== null ? (
          <>
            <Row label="Measured target" value={price(shape.target)}
                 help={isFlag ? "the pole, projected" : "the shape's own height"} />
            {shape.r_multiple !== null && (
              <Row label="Reward against risk" value={ratio(shape.r_multiple, 1)} />
            )}
          </>
        ) : null}

        {isFlag && shape.pole_pct !== null ? (
          <Row
            label="The pole"
            value={`${shape.pole_pct > 0 ? "+" : ""}${shape.pole_pct.toFixed(1)}%`}
            help={shape.pole_sessions ? `over ${shape.pole_sessions} sessions` : undefined}
          />
        ) : null}

        {!isSqueeze && !isFlag && (
          <Row label="Lines closed" value={`${Math.round(100 * (1 - shape.convergence))}%`}
               help="of the gap they started with" />
        )}

        {shape.apex_pct !== null ? (
          <Row label="Through to the apex" value={`${shape.apex_pct.toFixed(0)}%`} />
        ) : !isSqueeze && (
          <Row label="Through to the apex" value="n/a"
               help="the lines run parallel, so they never meet" />
        )}

        {isSqueeze && shape.momentum !== null && (
          <Row
            label="Leaning"
            value={shape.momentum > 0 ? "up" : "down"}
            help={shape.momentum_slope === null ? undefined
              : shape.momentum_slope > 0 ? "and strengthening" : "and easing"}
          />
        )}

        {!isSqueeze && (
          <Row label="Touches" value={`${shape.touches.upper} up · ${shape.touches.lower} down`}
               help="swing points the lines are drawn through" />
        )}
        <Row label="Length" value={`${shape.weeks.toFixed(1)} weeks`} />
      </div>

      {isSqueeze && shape.momentum !== null && (
        <p className="caption dim" style={{ margin: 0 }}>
          Leaning is where price has been sitting against its own range while
          the range was quiet. It is not a forecast of which way the range
          opens up, and this site has no measurement that would support one.
        </p>
      )}
    </div>
  );
}
