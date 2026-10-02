"""Tidy observation model shared by all sources."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Obs:
    series: str  # canonical series id, e.g. "gold_usd_oz" (see catalog.SERIES)
    area: str  # ISO 3166-1 alpha-3, or "WLD" for world prices
    period: str  # "2025" (annual), "2025-08" (monthly)
    value: float
    snapshot: str  # key of the raw snapshot this value was parsed from
    note: str = ""


@dataclass
class Store:
    """All observations, indexed for lookups by (series, area, period)."""

    items: dict[tuple[str, str, str], Obs] = field(default_factory=dict)

    def add(self, obs: Obs) -> None:
        key = (obs.series, obs.area, obs.period)
        prev = self.items.get(key)
        if prev is not None and abs(prev.value - obs.value) > 1e-9 * max(1.0, abs(obs.value)):
            raise ValueError(f"conflicting values for {key}: {prev.value} ({prev.snapshot}) vs {obs.value} ({obs.snapshot})")
        self.items[key] = obs

    def extend(self, observations) -> None:
        for o in observations:
            self.add(o)

    def get(self, series: str, area: str, period: str) -> Obs | None:
        return self.items.get((series, area, period))

    def series(self, series: str, area: str) -> dict[str, Obs]:
        return {p: o for (s, a, p), o in self.items.items() if s == series and a == area}

    def areas(self, series: str) -> set[str]:
        return {a for (s, a, _), _o in self.items.items() if s == series}

    def by_series(self) -> dict[str, list[Obs]]:
        out: dict[str, list[Obs]] = defaultdict(list)
        for (s, _a, _p), o in self.items.items():
            out[s].append(o)
        return out


def annual_mean(monthly: dict[str, Obs], year: str) -> tuple[float, int] | None:
    """Simple mean of the 12 monthly values of a year; None unless all 12 exist."""
    vals = [monthly[f"{year}-{m:02d}"].value for m in range(1, 13) if f"{year}-{m:02d}" in monthly]
    if len(vals) != 12:
        return None
    return sum(vals) / 12, 12
