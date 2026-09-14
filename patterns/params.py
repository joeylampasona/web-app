"""One schema for every detector threshold.

Nothing downstream hardcodes a number: the Learn page funnel, the custom-screen
dial panel and the detectors themselves all read this file, so the explanation
on the site can never drift from the code that produced the list.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from data import settings


@dataclass(frozen=True)
class ParamSpec:
    key: str
    label: str                 # plain English, sentence case
    kind: str                  # number | integer | percent | boolean
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    unit: str = ""
    funnel_title: str = ""     # step title in "How we narrow the market down"
    funnel_text: str = ""      # uses {value}
    help: str = ""             # the (i) tooltip

    def to_json(self) -> dict:
        out = asdict(self)
        out["value"] = self.default
        return out


@dataclass(frozen=True)
class Concept:
    title: str
    text: str
    anchor: str                # id of the matching element in the Learn SVG


@dataclass(frozen=True)
class ScreenSpec:
    key: str
    name: str
    shape: str                 # one line describing the shape
    description: str           # the paragraph above the card list
    params: list[ParamSpec]
    concepts: list[Concept] = field(default_factory=list)

    def defaults(self) -> dict[str, Any]:
        return {p.key: p.default for p in self.params}

    def spec_by_key(self) -> dict[str, ParamSpec]:
        return {p.key: p for p in self.params}

    def to_json(self) -> dict:
        return {
            "key": self.key, "name": self.name, "shape": self.shape,
            "description": self.description,
            "params": [p.to_json() for p in self.params],
            "concepts": [asdict(c) for c in self.concepts],
        }


class Params:
    """Resolved values for one screen: defaults, config overrides, then caller."""

    def __init__(self, screen: str, overrides: dict[str, Any] | None = None) -> None:
        spec = SCREENS[screen]
        self.screen = screen
        self.spec = spec
        values = spec.defaults()
        values.update((settings.get("patterns.overrides", {}) or {}).get(screen, {}) or {})
        values.update(overrides or {})
        self._values = values

    def __getattr__(self, item: str) -> Any:
        try:
            return self.__dict__["_values"][item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def has(self, key: str) -> bool:
        return key in self._values

    def to_json(self) -> dict[str, Any]:
        return dict(self._values)


# ---------------------------------------------------------------- shared specs

def _base_lookback(default_weeks: int, maximum: int) -> ParamSpec:
    return ParamSpec(
        key="base_lookback_weeks", label="How far back to look for the ceiling",
        kind="integer", default=default_weeks, minimum=4, maximum=maximum, step=1,
        unit="weeks",
        funnel_title="Where we look for the ceiling",
        funnel_text="The pivot is the highest price of the last {value} weeks.",
        help="The window we search for the price the stock has to clear. A longer "
             "window finds older, larger structures.")


_MIN_BASE = ParamSpec(
    key="min_base_weeks", label="Shortest base we'll accept", kind="integer",
    default=3, minimum=1, maximum=104, step=1, unit="weeks",
    funnel_title="Long enough to be a base",
    funnel_text="The base has lasted at least {value} weeks.",
    help="How long the stock has been going sideways. Shorter stretches are noise "
         "rather than structure.")

_MAX_DEPTH = ParamSpec(
    key="max_base_depth_pct", label="Deepest base we'll accept", kind="percent",
    default=35, minimum=5, maximum=70, step=1, unit="%",
    funnel_title="Not a collapse",
    funnel_text="From its ceiling, the base never fell more than {value}%.",
    help="How far price dropped inside the base, measured from the ceiling to the "
         "lowest point. Deeper structures take longer to repair.")

_NEAR_PIVOT = ParamSpec(
    key="max_from_pivot_pct", label="How far below the pivot we still list it",
    kind="percent", default=20, minimum=1, maximum=60, step=1, unit="%",
    funnel_title="Near the trigger",
    funnel_text="Price is no more than {value}% below the pivot.",
    help="How close the stock currently sits to the price it has to clear.")

_MIN_RS = ParamSpec(
    key="min_rs", label="Lowest RS rating we'll accept", kind="integer",
    default=70, minimum=1, maximum=99, step=1, unit="",
    funnel_title="Leadership",
    funnel_text="Relative strength rating of {value} or better.",
    help="Where the stock's 3, 6 and 12-month return ranks against every other name "
         "in the universe, 1 to 99. This is the one filter with published "
         "statistical support behind it.")

_FRESH = ParamSpec(
    key="fresh_breakout_sessions", label="How recent counts as fresh", kind="integer",
    default=5, minimum=1, maximum=20, step=1, unit="sessions",
    funnel_title="", funnel_text="",
    help="A breakout stays in the fresh bucket for this many sessions before it "
         "moves to climbing.")


_TREND = ParamSpec(
    key="min_trend_rungs", label="Moving averages that must be in order",
    kind="integer", default=0, minimum=0, maximum=3, step=1, unit=" of 3",
    funnel_title="Its averages agree",
    funnel_text="At least {value} of the three rungs hold — 9 above 21, 21 above "
                "50, 50 above 200.",
    help="The 9, 21, 50 and 200-day averages, fastest to slowest. Three of three "
         "is a full stack: every timeframe pointing the same way. Zero turns this "
         "off, which is where it starts, so no screen changes until you move it. "
         "A stock with under 200 sessions of history has no 200-day average and "
         "is not judged on this at all.")


_SWING = ParamSpec(
    key="swing_threshold_pct", label="Smallest swing that counts as a contraction",
    kind="percent", default=3.0, minimum=1.0, maximum=12.0, step=0.5, unit="%",
    funnel_title="", funnel_text="",
    help="A move smaller than this is treated as noise rather than as a pullback, "
         "so the contraction list stays readable.")


SCREENS: dict[str, ScreenSpec] = {
    "vcp": ScreenSpec(
        key="vcp",
        name="VCP",
        shape="A leader pauses, and each pullback inside the pause is shallower than "
              "the one before it.",
        description="This screen looks for a stock that has already been going up, "
                    "then stops and goes sideways for a few weeks. Inside that "
                    "pause the swings get smaller and the volume dries up. The top "
                    "of the pause is the pivot — the price it would have to clear. "
                    "The shape is a way of timing and describing a stock, not a "
                    "forecast: in our own out-of-sample work the structural parts "
                    "of this pattern carried no measurable edge, and relative "
                    "strength did.",
        params=[
            _MIN_RS,
            ParamSpec(key="require_above_50ma", label="Must be above its 50-day line",
                      kind="boolean", default=True,
                      funnel_title="Above its 50-day line",
                      funnel_text="Price is above the average of the last 50 days.",
                      help="The average closing price of the last 50 sessions."),
            ParamSpec(key="require_above_200ma", label="Must be above its 200-day line",
                      kind="boolean", default=True,
                      funnel_title="Above its 200-day line",
                      funnel_text="Price is above the average of the last 200 days.",
                      help="The average closing price of the last 200 sessions."),
            ParamSpec(key="max_from_52w_high_pct",
                      label="Furthest below the 52-week high we'll accept",
                      kind="percent", default=30, minimum=5, maximum=60, step=1, unit="%",
                      funnel_title="Still near its highs",
                      funnel_text="Within {value}% of its highest price of the last year.",
                      help="How far the stock sits below its best price of the last year."),
            _base_lookback(24, 104),
            _MIN_BASE,
            _MAX_DEPTH,
            ParamSpec(key="max_second_half_atr_ratio",
                      label="Swings must tighten by", kind="number", default=0.9,
                      minimum=0.5, maximum=1.2, step=0.05, unit="×",
                      funnel_title="The swings tighten",
                      funnel_text="The second half of the base swings no more than "
                                  "{value}× as much as the first half.",
                      help="Average daily range in the back half of the base compared "
                           "with the front half. The card shows the same thing the "
                           "other way up, so 1.3× there means noticeably tighter."),
            ParamSpec(key="max_second_half_volume_ratio",
                      label="Volume must dry up by", kind="number", default=0.9,
                      minimum=0.4, maximum=1.2, step=0.05, unit="×",
                      funnel_title="Volume dries up",
                      funnel_text="The second half of the base trades no more than "
                                  "{value}× the volume of the first half.",
                      help="Shares traded in the back half of the base against the "
                           "front half. The card shows the reciprocal, so a bigger "
                           "number there means quieter."),
            _NEAR_PIVOT, _SWING, _FRESH, _TREND,
        ],
        concepts=[
            Concept("Prior uptrend", "The stock was already going up before the pause "
                                     "started.", "uptrend"),
            Concept("The base", "A stretch of weeks where it goes sideways instead of "
                                "up.", "base"),
            Concept("Contractions", "Each pullback inside the base is shallower than "
                                    "the one before it.", "contractions"),
            Concept("Volume dry-up", "Fewer shares change hands as the base gets "
                                     "tighter.", "volume"),
            Concept("The pivot", "The ceiling at the top of the base — the price it "
                                 "has to clear.", "pivot"),
            Concept("Breakout", "A close above the pivot.", "breakout"),
            Concept("Climbing", "It cleared the pivot earlier and is still above its "
                                "trailing line.", "climbing"),
        ],
    ),
    "blue_sky": ScreenSpec(
        key="blue_sky",
        name="Blue sky",
        shape="A stock resting at the highest price it has ever traded, with nothing "
              "above it.",
        description="This screen looks for a stock sitting at the highest price in its "
                    "history. Above the pivot there are no prior owners waiting to get "
                    "out at break-even, because nobody ever paid more. It is a "
                    "description of where the stock sits, not a claim about where it "
                    "goes next.",
        params=[
            _MIN_RS,
            _base_lookback(52, 260),
            _MIN_BASE,
            ParamSpec(key="max_base_depth_pct", label="Deepest base we'll accept",
                      kind="percent", default=25, minimum=5, maximum=60, step=1, unit="%",
                      funnel_title="A shallow rest, not a fall",
                      funnel_text="From its ceiling, the base never fell more than {value}%.",
                      help="A rest at the high should be shallow. A deep one is a top "
                           "forming, not a base."),
            ParamSpec(key="all_time_high_tolerance_pct",
                      label="How close to the all-time high the pivot must be",
                      kind="percent", default=2, minimum=0, maximum=15, step=0.5, unit="%",
                      funnel_title="Nothing traded above it",
                      funnel_text="The pivot is within {value}% of the highest price "
                                  "the stock has ever traded.",
                      help="We compare the pivot against every session we hold for this "
                           "stock. Our history goes back as far as our data does, which "
                           "is not necessarily the whole life of the company."),
            _NEAR_PIVOT, _SWING, _FRESH, _TREND,
        ],
        concepts=[
            Concept("Blue sky", "There is no price history above the pivot.", "opensky"),
            Concept("No trapped sellers", "Nobody who owns it is underwater, so nobody "
                                          "is waiting to get out at break-even.", "trapped"),
            Concept("Basing at the high", "It is resting at the top rather than "
                                          "falling away from it.", "base"),
            Concept("The pivot", "The all-time high — the price it has to clear.", "pivot"),
            Concept("Breakout", "A close into new highs.", "breakout"),
            Concept("Climbing", "It cleared the pivot earlier and is still above its "
                                "trailing line.", "climbing"),
        ],
    ),
    "multi_year": ScreenSpec(
        key="multi_year",
        name="Multi-year / deep comeback",
        shape="A lid that has held for a year or more, with the stock turning back up "
              "underneath it.",
        description="This screen looks for a stock that has spent a year or more going "
                    "nowhere and has started to turn back up. The pivot is the lid of "
                    "that long stretch. These take a long time to set up and the wait "
                    "is the point; the screen tells you where the lid is, not whether "
                    "it will break.",
        params=[
            ParamSpec(key="min_rs", label="Lowest RS rating we'll accept", kind="integer",
                      default=60, minimum=1, maximum=99, step=1,
                      funnel_title="Strength returning",
                      funnel_text="Relative strength rating of {value} or better.",
                      help="Where the stock's 3, 6 and 12-month return ranks against "
                           "the universe, 1 to 99."),
            ParamSpec(key="require_above_200ma", label="Must be above its 200-day line",
                      kind="boolean", default=True,
                      funnel_title="Turning up",
                      funnel_text="Price is back above the average of the last 200 days.",
                      help="The average closing price of the last 200 sessions."),
            # 78 rather than 104: the window has to be meaningfully shorter than
            # the history available, or there is nowhere for a breakout to sit
            # after a year-long base. On two years of data a 104-week window left
            # exactly one valid position and the screen returned nothing but
            # forming setups. Raise it again once the history goes deeper.
            _base_lookback(78, 300),
            ParamSpec(key="min_base_weeks", label="Shortest base we'll accept",
                      kind="integer", default=52, minimum=26, maximum=200, step=1,
                      unit="weeks",
                      funnel_title="The long wait",
                      funnel_text="The lid has held for at least {value} weeks.",
                      help="How long the stock has been capped by the same price."),
            ParamSpec(key="max_base_depth_pct", label="Deepest base we'll accept",
                      kind="percent", default=60, minimum=10, maximum=90, step=1, unit="%",
                      funnel_title="Not a permanent impairment",
                      funnel_text="From the lid, it never fell more than {value}%.",
                      help="A long base is allowed to be deep. Past a point it is a "
                           "different company than the one that set the high."),
            _NEAR_PIVOT, _SWING, _FRESH, _TREND,
        ],
        concepts=[
            Concept("The long wait", "The same price has capped the stock for a year "
                                     "or more.", "base"),
            Concept("Above the 200-day line", "It has climbed back above its long "
                                              "average.", "ma200"),
            Concept("Strength returning", "Its ranking against the rest of the market "
                                          "is improving.", "strength"),
            Concept("The pivot", "The lid of a very old base.", "pivot"),
            Concept("Breakout", "A close through a lid that held a year or more.",
                    "breakout"),
            Concept("Climbing", "It cleared the lid earlier and is still above its "
                                "trailing line.", "climbing"),
        ],
    ),
    "ipo": ScreenSpec(
        key="ipo",
        name="IPO base",
        shape="A recent listing building its first real base, holding above its 50-day "
              "line.",
        description="This screen looks for a company that listed recently and is "
                    "building its first proper base. There is no relative strength dial "
                    "on this screen at all — a young listing has not been trading long "
                    "enough for a twelve-month ranking to mean anything, and we would "
                    "rather show you nothing than a number we made up.",
        params=[
            ParamSpec(key="max_weeks_listed", label="Longest since listing we'll accept",
                      kind="integer", default=50, minimum=4, maximum=156, step=1,
                      unit="weeks",
                      funnel_title="Recently listed",
                      funnel_text="On the market for less than {value} weeks.",
                      help="Measured from the listing date, or from the first session "
                           "we hold for the stock."),
            _base_lookback(26, 104),
            _MIN_BASE, _MAX_DEPTH,
            ParamSpec(key="require_above_50ma", label="Must be above its 50-day line",
                      kind="boolean", default=True,
                      funnel_title="Holding its 50-day line",
                      funnel_text="Price is above the average of the last 50 days.",
                      help="The average closing price of the last 50 sessions. For a "
                           "young listing this is the only trend line with enough "
                           "history to mean anything."),
            _NEAR_PIVOT, _SWING, _FRESH, _TREND,
        ],
        concepts=[
            Concept("Recently listed", "The company has been public for under a year. "
                                       "There is no RS dial on this screen, because a "
                                       "young listing has not had the twelve months "
                                       "relative strength needs.", "listing"),
            Concept("Its first real base", "Its first stretch of weeks going sideways "
                                           "instead of up.", "base"),
            Concept("Holding its 50-day line", "It is staying above its short trend "
                                               "line while it rests.", "ma50"),
            Concept("The pivot", "The top of that first base.", "pivot"),
            Concept("Breakout", "A close above the top of the first base.", "breakout"),
            Concept("Climbing", "It cleared the pivot earlier and is still above its "
                                "trailing line.", "climbing"),
        ],
    ),

    "flat_base": ScreenSpec(
        key="flat_base",
        name="Flat base",
        shape="A shallow, level shelf near the highs — the tightest kind of pause.",
        description="This screen looks for a stock that has gone sideways in a narrow "
                    "band, close to its highs, without giving much back. A flat base is "
                    "the shallowest of the pauses on this site: the whole point is that "
                    "very little happened. It has to be level as well as shallow — a "
                    "shelf that drifts steadily lower through its own span is a slow "
                    "decline, not a rest, so that is measured separately and excluded. "
                    "As with every screen here, the shape is a way of describing and "
                    "timing a stock, not a forecast.",
        params=[
            _MIN_RS,
            _base_lookback(26, 104),
            ParamSpec(key="min_base_weeks", label="Shortest shelf we'll accept",
                      kind="integer", default=5, minimum=3, maximum=40, step=1,
                      unit="weeks",
                      funnel_title="Long enough to be a shelf",
                      funnel_text="It has gone sideways for at least {value} weeks.",
                      help="Fewer than three weeks is a quiet patch, not a base."),
            ParamSpec(key="max_base_depth_pct", label="Deepest shelf we'll accept",
                      kind="percent", default=15, minimum=5, maximum=30, step=1,
                      unit="%",
                      funnel_title="Shallow",
                      funnel_text="From the top of the shelf it never fell more "
                                  "than {value}%.",
                      help="Shallowness is the whole point. Past about 15% it is an "
                           "ordinary base rather than a flat one."),
            ParamSpec(key="max_downward_drift_pct",
                      label="Most it may sag across the shelf", kind="percent",
                      default=4, minimum=0, maximum=15, step=1, unit="%",
                      funnel_title="Level, not sagging",
                      funnel_text="The second half's lows sit no more than {value}% "
                                  "below the first half's.",
                      help="A shelf that steps quietly lower the whole way through is "
                           "a decline in slow motion. This is what tells them apart."),
            ParamSpec(key="require_above_50ma", label="Must be above its 50-day line",
                      kind="boolean", default=True,
                      funnel_title="Above its 50-day line",
                      funnel_text="Price is above the average of the last 50 days.",
                      help="The average closing price of the last 50 sessions."),
            ParamSpec(key="max_from_52w_high_pct",
                      label="Furthest below its 52-week high", kind="percent",
                      default=20, minimum=5, maximum=60, step=1, unit="%",
                      funnel_title="Near its highs",
                      funnel_text="Within {value}% of its highest price in a year.",
                      help="A flat base far below the highs is a stock that has "
                           "stopped falling, which is a different thing."),
            _NEAR_PIVOT, _SWING, _FRESH, _TREND,
        ],
        concepts=[
            Concept("A shelf", "Weeks of going sideways in a narrow band instead of "
                               "up or down.", "base"),
            Concept("Shallow", "It never fell far from the top of that band.", "depth"),
            Concept("Level", "The second half sits at much the same height as the "
                             "first, rather than stepping lower.", "drift"),
            Concept("The pivot", "The top of the shelf.", "pivot"),
            Concept("Breakout", "A close above the top of the shelf.", "breakout"),
            Concept("Climbing", "It cleared the pivot earlier and is still above its "
                                "trailing line.", "climbing"),
        ],
    ),

    "cup_and_handle": ScreenSpec(
        key="cup_and_handle",
        name="Cup and handle",
        shape="A rounded bottom, then a small pause just below the lid.",
        description="This screen looks for a stock that fell away, curved back up over "
                    "several weeks, and then paused briefly near the top of that curve. "
                    "The curve is the cup and the pause is the handle. Three things are "
                    "checked rather than assumed: the low sits in the middle of the "
                    "base and not at either edge, because a low at the left edge is a "
                    "recovery and a low at the right edge is still a fall; both sides "
                    "come back to a similar height; and the pause near the end is "
                    "shallow and sits high in the cup, because a deep late drop is a "
                    "second leg down. It is the most recognisable shape here and, like "
                    "the others, it is a description rather than a forecast.",
        params=[
            _MIN_RS,
            _base_lookback(40, 104),
            ParamSpec(key="min_base_weeks", label="Shortest cup we'll accept",
                      kind="integer", default=7, minimum=5, maximum=60, step=1,
                      unit="weeks",
                      funnel_title="Long enough to round out",
                      funnel_text="The cup has taken at least {value} weeks.",
                      help="A curve needs time. Anything faster is a dip, and it "
                           "cannot round."),
            _MAX_DEPTH,
            ParamSpec(key="min_time_at_lows",
                      label="How much of the cup is spent near the bottom",
                      kind="percent", default=0.18, minimum=0.05, maximum=0.5,
                      step=0.01, unit="",
                      funnel_title="Rounded, not a V",
                      funnel_text="At least {value} of the sessions closed in the "
                                  "lower part of the cup.",
                      help="A V has its low in the middle too. What separates them is "
                           "time: a cup lingers near the bottom, a V passes through it "
                           "in a few days."),
            ParamSpec(key="max_rim_gap_pct", label="Furthest a rim may sit below the lid",
                      kind="percent", default=8, minimum=2, maximum=25, step=1, unit="%",
                      funnel_title="Both rims near the lid",
                      funnel_text="Neither side of the cup sits more than {value}% "
                                  "below the top.",
                      help="If the left side is far lower, the stock is still climbing "
                           "back to where it was rather than rounding out."),
            ParamSpec(key="max_handle_weeks", label="Longest handle we'll accept",
                      kind="integer", default=4, minimum=1, maximum=12, step=1,
                      unit="weeks",
                      funnel_title="A brief handle",
                      funnel_text="The pause at the end lasted no more than "
                                  "{value} weeks.",
                      help="A pause that runs for months is not a handle, it is "
                           "another base."),
            ParamSpec(key="max_handle_depth_pct", label="Deepest handle we'll accept",
                      kind="percent", default=15, minimum=5, maximum=35, step=1,
                      unit="%",
                      funnel_title="A shallow handle",
                      funnel_text="The pause gave back no more than {value}% of its "
                                  "own range.",
                      help="A deep drop at the end is a second leg down, not a rest."),
            ParamSpec(key="min_handle_position",
                      label="How high in the cup the handle must sit", kind="percent",
                      default=0.5, minimum=0.2, maximum=0.9, step=0.05, unit="",
                      funnel_title="High in the cup",
                      funnel_text="The handle's low sits at least {value} of the way "
                                  "up from the bottom of the cup.",
                      help="0.5 means the handle never dipped below the middle of the "
                           "cup. Back at the bottom, it is not a handle."),
            ParamSpec(key="require_above_50ma", label="Must be above its 50-day line",
                      kind="boolean", default=True,
                      funnel_title="Above its 50-day line",
                      funnel_text="Price is above the average of the last 50 days.",
                      help="The average closing price of the last 50 sessions."),
            _NEAR_PIVOT, _SWING, _FRESH, _TREND,
        ],
        concepts=[
            Concept("The cup", "A fall and a gradual curve back up over several "
                               "weeks.", "base"),
            Concept("Rounded, not V-shaped", "The low sits in the middle of the span, "
                                             "so it curved rather than snapped back.",
                    "rounding"),
            Concept("The rims", "The two sides of the cup, both near the same "
                                "height.", "rim"),
            Concept("The handle", "A short, shallow pause near the top of the cup "
                                  "before it tries to clear it.", "handle"),
            Concept("The pivot", "The top of the cup.", "pivot"),
            Concept("Breakout", "A close above that lid.", "breakout"),
        ],
    ),
}

SCREEN_KEYS = list(SCREENS.keys())


def funnel_steps(screen: str, overrides: dict[str, Any] | None = None) -> list[dict]:
    """The numbered filter funnel, generated so it cannot drift from the code."""
    spec = SCREENS[screen]
    params = Params(screen, overrides)
    steps: list[dict] = [{
        "title": "The liquid US universe",
        "text": (f"US common stocks over ${settings.get('universe.min_price', 5):,.0f}, "
                 f"market cap over ${settings.get('universe.min_market_cap', 3e8)/1e6:,.0f}M, "
                 f"and at least ${settings.get('universe.min_avg_dollar_volume', 5e6)/1e6:,.0f}M "
                 f"traded a day over the last "
                 f"{settings.get('universe.dollar_volume_lookback', 20)} sessions."),
        "key": "universe",
    }]
    for p in spec.params:
        if not p.funnel_title:
            continue
        value = params.get(p.key)
        if p.kind == "boolean" and not value:
            continue
        # A numeric gate at zero admits everything. Printing it as a step would
        # describe a filter that is not filtering.
        if p.kind in ("integer", "percent") and not value and p.minimum == 0:
            continue
        steps.append({
            "title": p.funnel_title,
            "text": p.funnel_text.replace("{value}", _format(value, p)),
            "key": p.key,
        })
    return steps


def _format(value: Any, spec: ParamSpec) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value != int(value):
        return f"{value:g}"
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def schema() -> dict:
    """Everything the dial panel and the Learn page need, in one payload."""
    return {key: spec.to_json() for key, spec in SCREENS.items()}
