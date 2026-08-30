// Utility tier: pure presentation helpers.
export class Formatter {
  /** Format a number as USD with a fixed number of decimal places. */
  static usd(value: number, dp = 4): string {
    return `$${Number(value).toFixed(dp)}`;
  }

  /** Format an ISO datetime string as a readable local date + time. */
  static dateTime(iso: string): string {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

}
