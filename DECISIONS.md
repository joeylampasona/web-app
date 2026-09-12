# Decisions, gaps and deviations

The brief lists a set of things it deliberately left open, and says to stop and
ask rather than invent them. This build was asked for in one go, so rather than
stop with nothing delivered, each gap below was filled with the most defensible
option and recorded here. **Every one of these is yours to overrule** — they are
all small, localised changes.

---

## Gaps from section 3, and what was built instead

| Gap | What was built | Where |
|---|---|---|
| **Grid vs list view on Screens** | The toggle is real. Cards is the default; List is a dense table — ticker, RS, close, vs pivot, base length, tightening, dry-up, stage. Compact cards were the other candidate and would be a small change. | `web/components/ScreenBrowser.tsx` |
| **Share button output** | Web Share API with a one-line summary and a link to the stock page, falling back to the clipboard. A rendered PNG of the chart plus metrics is the likelier answer and needs a decision. | `web/components/ShareButton.tsx` |
| **Industry and theme detail page** | One layout serves both: the group's RS, average member RS, leaders, fresh breakouts, the three RS-change windows, and the member table. Needed because the treemap and the rotation scatter both drill into it. | `web/components/GroupDetail.tsx` |
| **Guide and case study article layout** | Index only, as specced. Each card is marked "not written yet" rather than linking to a page that does not exist. Five honest article stubs seeded. | `web/content/reading.ts` |
| **Rotation "drag to trace a path"** | Skipped for v1, as instructed. | — |
| **"Ask a question" on the rotation map** | Skipped for v1, as instructed. | — |
| **Auth provider (Clerk vs Supabase)** | **Not chosen.** `lib/auth.tsx` is the seam: it reports signed-out and raises the sign-up sheet. Swap `signedIn`/`user` for the real client and all four gates start working without touching a component. The gates themselves are built and in place: watchlist, saved custom screens, export, X-ray. | `web/lib/auth.tsx` |
| **Subgroups** | Themes replace them, as the brief intends. | `config/themes.yaml` |

---

## Two deviations from the brief, both deliberate

**1. The legend on the VCP Learn schematic.** The brief specifies the wording
"up days (buying) / down days (selling)", and separately requires that the
words buy and sell never appear in the UI except the Learn page's step-1 label.
Those two lines conflict. The hard legal constraint wins: the legend reads
"up days (demand) / down days (supply)". Same for the backtest setting the
brief calls "Sell winners by", which reads "Exit winners by". Change either in
one line if your review disagrees.

**2. `SyntheticAdapter`.** Not in the brief. It exists because every
verification command and the entire web app need bars on disk, and no
credentials exist in this environment. It is a fixture, not a data source: a
fixed seed, invented tickers and company names — so no fabricated price series
is ever published under a real company's name — and a `synthetic_demo` stamp in
`meta.json` that the web app banners on every page. Point `data.provider` at
`polygon` and it disappears entirely.

---

## Judgement calls inside the specced scope

**Market-wide breakout counts.** Breadth's "broke out today" and "tested the
pivot and failed" use a screen-independent definition — a close above the
highest high of the prior 50 sessions — so the number means the same thing
whichever screen you are looking at. Screen-level breakout counts come from the
scan and are counted separately.

**Which gates a played-out name has to pass.** A setup that already broke out
is not asked to prove it is still near its pivot or still a leader. It is on
the screen so its outcome can be shown. The structural gates (base length,
depth, and the screen's own shape test) still apply to every stage.

**The custom-screen dial panel.** Every dial is generated from the detector
param schema. Five of them — the lookback window, the swing threshold, the
fresh-breakout window, the all-time-high tolerance and the listing-age limit —
decide *where the base is* before any published metric exists, so they cannot
be applied to an already published setup. They are shown, disabled, with the
reason stated, rather than quietly dropped from a panel that claims to be
generated from the schema. Making them live means a re-scan API route.

**Historical earnings dates in the backtest.** We only hold forward earnings
dates. When "skip earnings within 7 days" is on, historical ones are projected
backwards on a quarterly cadence from the next known date. That is an
approximation, it is stated in the run's notes, and it flags the affected
metrics provisional.

**Index additions and deletions.** The event type exists and stays empty. There
is no free automatic feed we are willing to depend on, and the alternative is
the hand-maintained events database the brief rules out.

**Read-through tags.** `supplier` is in the vocabulary and is never emitted.
We have no free supply-chain source, and asserting a supplier relationship we
cannot evidence would be inventing data. Peers in the same theme and the same
industry are tagged `competitor`; the rest are tagged `industry`. Only the
largest name in a theme emits read-throughs.

---

## Still open, and worth deciding before launch

1. **Verify the Polygon grouped daily endpoint on the free tier yourself.** It
   could not be confirmed from here and the whole free-tier premise rests on it.
2. **Pick the auth provider.** Four surfaces are waiting behind the seam.
3. **Decide the share payload.** PNG or link.
4. **Legal review of the copy.** Especially the two deviations above.
