#!/usr/bin/env python3
"""Enforce the colour rules that tokens.css states in prose.

The token file has claimed since it was written that the four moving-average
lines stay separable from each other and clear of gain, loss and the pivot.
Nothing checked it, so it was true only for as long as nobody changed a value
-- and the first accent change put four of those pairs under the line at once.

Run: python3 scripts/check_palette.py
Exits non-zero, naming every pair, when the palette stops holding.

Distances are CIEDE2000, which models how different two colours actually look
rather than how far apart their numbers are. Contrast is WCAG.
"""
from __future__ import annotations

import math
import pathlib
import re
import sys

TOKENS = pathlib.Path(__file__).resolve().parent.parent / "styles" / "tokens.css"

# The four lines are drawn at two widths: 9 and 21 thin, 50 and 200 thick.
# Only a pair sharing a width has nothing but colour to separate it, so only
# those two pairs carry a distance floor. Cross-width pairs deliberately gave
# up separation to buy it, because weight already tells them apart -- an
# earlier version of this script checked all six pairs and failed the shipped
# palette, which was the script being wrong, not the palette.
SAME_WIDTH_PAIRS = ((9, 21), (50, 200))
MA_PAIR_MIN = 30.0
# A line that could be read as "gain", "loss" or "the pivot" is worse than no
# line: those three already mean something specific everywhere else on the site.
MA_SEMANTIC_MIN = 30.0
# Gain and loss carry opposite meanings and must never be near each other.
SEMANTIC_MIN = 30.0


def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_lab(rgb):
    r, g, b = (_lin(c) for c in rgb)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29
    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def ciede2000(lab1, lab2) -> float:
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7))) if Cb > 0 else 0
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2)
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30))
         + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6))
         - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dTh = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7)) if Cbp > 0 else 0
    Sl = 1 + (0.015 * (Lbp - 50) ** 2) / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dTh)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                     + Rt * (dCp / Sc) * (dHp / Sh))


def de(a: str, b: str) -> float:
    return ciede2000(rgb_lab(hex_rgb(a)), rgb_lab(hex_rgb(b)))


def luminance(h: str) -> float:
    r, g, b = (_lin(c) for c in hex_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def parse_blocks(css: str) -> dict[str, dict[str, str]]:
    """Hex values per selector block. Later blocks inherit the :root defaults,
    which is how the light theme works -- it overrides a subset."""
    blocks: dict[str, dict[str, str]] = {}
    for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        name = selector.strip().splitlines()[-1].strip()
        if name not in (":root", '[data-theme="light"]'):
            continue
        found = dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;", body))
        blocks.setdefault(name, {}).update(found)
    root = blocks.get(":root", {})
    light = {**root, **blocks.get('[data-theme="light"]', {})}
    return {"dark": root, "light": light}


def check() -> int:
    themes = parse_blocks(TOKENS.read_text())
    problems: list[str] = []

    for theme, tok in themes.items():
        def get(name: str) -> str | None:
            return tok.get(name)

        mas = {w: get(f"--chart-ma-{w}") for w in (9, 21, 50, 200)}
        if any(v is None for v in mas.values()):
            problems.append(f"{theme}: a moving-average colour is missing")
            continue

        for a, bx in SAME_WIDTH_PAIRS:
            d = de(mas[a], mas[bx])
            if d < MA_PAIR_MIN:
                problems.append(
                    f"{theme}: MA {a} vs MA {bx} share a line width and are "
                    f"dE {d:.1f}, under {MA_PAIR_MIN}")

        semantics = {"gain": get("--gain"), "loss": get("--loss"),
                     "pivot": get("--chart-pivot")}
        for window, colour in mas.items():
            for label, other in semantics.items():
                if not other:
                    continue
                d = de(colour, other)
                if d < MA_SEMANTIC_MIN:
                    problems.append(
                        f"{theme}: MA {window} vs {label} is dE {d:.1f}, "
                        f"under {MA_SEMANTIC_MIN} -- a line that reads as {label}")

        pairs = [("gain", "loss"), ("gain", "brand"), ("loss", "brand"),
                 ("gain", "brand-ink"), ("loss", "brand-ink")]
        vals = {"gain": get("--gain"), "loss": get("--loss"),
                "brand": get("--brand"), "brand-ink": get("--brand-ink")}
        for a, bx in pairs:
            if vals[a] and vals[bx]:
                d = de(vals[a], vals[bx])
                if d < SEMANTIC_MIN:
                    problems.append(
                        f"{theme}: {a} vs {bx} is dE {d:.1f}, under {SEMANTIC_MIN}")

        # Ink that has to be readable where it is actually used.
        surface = get("--surface-1")
        # --brand is a fill now, so its readability as text is not the test;
        # --brand-ink is what lands on a card as text, and --on-brand is what
        # lands on the fill.
        for name, need in (("--text-primary", 4.5), ("--text-secondary", 4.5),
                           ("--text-muted", 3.0), ("--brand-ink", 3.0)):
            colour = get(name)
            if colour and surface:
                r = contrast(colour, surface)
                if r < need:
                    problems.append(
                        f"{theme}: {name} on --surface-1 is {r:.2f}:1, under {need}")

        fill, ink_on_fill = get("--brand"), get("--on-brand")
        if fill and ink_on_fill:
            r = contrast(ink_on_fill, fill)
            if r < 4.5:
                problems.append(
                    f"{theme}: --on-brand on the --brand fill is {r:.2f}:1, under 4.5")

        # Everything that lands on the hero slab, which is dark in both themes.
        slab = themes["dark"].get("--on-dark-bg")
        if slab:
            for name, need in (("--on-dark-ink", 4.5), ("--on-dark-muted", 4.5),
                               ("--on-dark-dim", 3.0), ("--on-dark-brand", 3.0),
                               ("--on-dark-gain", 3.0), ("--on-dark-loss", 3.0)):
                colour = themes["dark"].get(name)
                if colour:
                    r = contrast(colour, slab)
                    if r < need:
                        problems.append(
                            f"hero: {name} on the slab is {r:.2f}:1, under {need}")
            break  # slab checks are theme-independent; run them once

    if problems:
        print("PALETTE FAILS:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("palette holds: MA lines separable, semantics distinct, ink readable")
    return 0


if __name__ == "__main__":
    sys.exit(check())
