/**
 * Whether a set of delayed quotes is older than the close the pages already
 * show.
 *
 * A delayed quote exists to say where price is now, against a pivot measured
 * at the last close. Once the nightly has published a later session, a quote
 * from the session before is not a sharper figure, it is an older one, and
 * laying it over the page replaces Friday's close with Thursday's. That is
 * what happened when the sweep was refused for a whole session: the last file
 * it had written stayed up and kept overriding every close published after it.
 *
 * Compared by New York date, because that is the day a session belongs to.
 * The same day is kept: an after-the-bell sweep and that night's close are the
 * same figure.
 */
const NEW_YORK_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/New_York",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function quotesAreStale(
  fetchedAt: string | null | undefined,
  asOf: string | null | undefined,
): boolean {
  // Nothing to compare against is not staleness. A set with no timestamp is
  // kept, as it was before this check existed.
  if (!fetchedAt || !asOf) return false;
  const when = new Date(fetchedAt);
  if (Number.isNaN(when.getTime())) return false;
  return NEW_YORK_DAY.format(when) < asOf;
}
