import { useMemo, type ReactNode } from "react";
import type { Scope } from "../App";
import { useI18n } from "../i18n";
import { countryName } from "../lib";
import type { Country, CountryYear } from "../types";

export interface Row {
  iso: string;
  c: Country;
  name: string;
  year: string;
  row: CountryYear;
}

/** Economies in scope (G20 members or all, plus the focus economies) with data for the year. */
export function useRows(scope: Scope): Row[] {
  const { ds, year, group, picks } = scope;
  const i = useI18n();
  return useMemo(
    () =>
      Object.entries(ds.countries)
        .filter(([iso, c]) => group === "all" || c.g20 || picks.includes(iso))
        .flatMap(([iso, c]) => (c.years[year] ? [{ iso, c, name: countryName(i, c), year, row: c.years[year] }] : [])),
    [ds, year, group, picks, i],
  );
}

/** Map a clicked chart category (an economy's name) back to its code and toggle its focus. */
export function usePickByName(rows: Row[], togglePick: (iso: string) => void) {
  return useMemo(() => {
    const byName = new Map(rows.map((r) => [r.name, r.iso]));
    return (name: string) => {
      const iso = byName.get(name);
      if (iso) togglePick(iso);
    };
  }, [rows, togglePick]);
}

/** "label: value" in the reader's language. */
export function useKV() {
  const i = useI18n();
  return (label: string, value: string) => i.t("u.kv", { k: label, v: value });
}

/** Legend of a ranking: focus economies vs the others, or one entry when none is in focus
 *  (then every bar is drawn alike). */
export function Legend({ anyFocus, focus, others, all, extra }: {
  anyFocus: boolean; focus: string; others: string; all: string; extra?: ReactNode;
}) {
  return (
    <div className="legend">
      {anyFocus ? (
        <>
          <span><span className="sw" style={{ background: "var(--accent)" }} />{focus}</span>
          <span><span className="sw" style={{ background: "var(--deemph)" }} />{others}</span>
        </>
      ) : (
        <span><span className="sw" style={{ background: "var(--accent)" }} />{all}</span>
      )}
      {extra}
    </div>
  );
}
