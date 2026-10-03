from wagegold import build
from wagegold.config import GRAMS_PER_TROY_OUNCE
from wagegold.model import Obs, Store, annual_mean


def test_annual_mean_requires_twelve_months():
    s = Store()
    for m in range(1, 12):
        s.add(Obs("x", "WLD", f"2025-{m:02d}", m, "t"))
    assert annual_mean(s.series("x", "WLD"), "2025") is None
    s.add(Obs("x", "WLD", "2025-12", 12, "t"))
    assert annual_mean(s.series("x", "WLD"), "2025") == (6.5, 12)


def test_store_rejects_conflicting_values():
    s = Store()
    s.add(Obs("x", "USA", "2025", 1.0, "a"))
    s.add(Obs("x", "USA", "2025", 1.0, "b"))  # same value from another snapshot is fine
    try:
        s.add(Obs("x", "USA", "2025", 2.0, "c"))
    except ValueError:
        return
    raise AssertionError("conflict not detected")


def test_chain_identity():
    gold_usd_g = 3441.5 / GRAMS_PER_TROY_OUNCE
    fx, ppp = 7.19, 3.46
    v = build.WageVariant("k", "l", "mean", "s", None, 60.0, None, "m", [])
    w = build.wage_metrics(v, gold_usd_g * fx, fx, ppp, 12.6)
    pli = ppp / fx
    assert abs(w["hourly_gold_g"] * (gold_usd_g / pli) - w["hourly_ppp"]) < 1e-12
    assert abs(w["minutes_per_cohd_day"] - 12.6 / 60 * 60) < 1e-12


def _walk(part):
    """Every message (dict) and raw string inside a message part."""
    if isinstance(part, dict):
        yield part
        for v in part.get("p", {}).values():
            yield from _walk(v)
    elif isinstance(part, list):
        for x in part:
            yield from _walk(x)
    elif isinstance(part, str):
        yield part


def _keys(part):
    return {m["k"] for m in _walk(part) if isinstance(m, dict)}


def _texts(part):
    return [x for x in _walk(part) if isinstance(x, str)]


def _params(part, key):
    return [m.get("p", {}) for m in _walk(part) if isinstance(m, dict) and m["k"] == key]


DIC = {"note_indicator": {
    "T8:127": "Central tendency measure: Mean", "T8:128": "Central tendency measure: Median",
    "T9:133": "Value type: Nominal values", "T9:131": "Value type: Real values",
    "T30:1": "Currency: XXX - Euro (EUR)", "T30:2": "Currency: XXX - Old unit (OLD)",
    "S4:31": "Geographical coverage: Urban areas only",
}, "note_source": {}, "source": {}}
META = {a: {"is_economy": True, "name_en": a} for a in ("AAA", "BBB")}


def _store(*obs):
    s = Store()
    s.extend(Obs(*o) if isinstance(o, tuple) else o for o in obs)
    return s


def _wdi(area, year, fx, ppp, lcu_unit_fx=None):
    """WDI rows for one economy-year; lcu_unit_fx = the conversion factor in WDI's LCU unit."""
    f = lcu_unit_fx if lcu_unit_fx is not None else fx
    return [("fx_lcu_usd", area, year, fx, "s"), ("ppp_hfce", area, year, ppp, "s"),
            ("gdp_lcu", area, year, f * 1e12, "s"), ("gdp_usd", area, year, 1e12, "s"),
            ("hfce_lcu", area, year, ppp * 500, "s"), ("hfce_intl", area, year, 500.0, "s")]


def test_units_official_rate_in_other_unit_is_not_used():
    # Pre-euro year: the official rate is in the legacy unit (×200), WDI's LCU series in euro.
    s = _store(*_wdi("AAA", "2005", 200.0, 0.6, lcu_unit_fx=1.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2005", 1500.0, "s", "T8:127 T9:133 T30:1"),
               Obs("ilo_monthly_mean_ppp@X:1", "AAA", "2005", 2500.0, "s"))
    u = build.UnitGraph(s, DIC, ["2005"], META)
    g = u.year("AAA", "2005")
    assert not g.linked("F") and g.linked("P") and g.linked("ilo:ilo_monthly_mean@X:1")
    assert u.currency("AAA") == "EUR"
    u.explain("AAA", "2005", True)
    assert any(e["scope"] == "fx" for e in u.log)


def test_units_wage_in_old_currency_is_left_out():
    s = _store(*_wdi("AAA", "2018", 8.0, 3.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2018", 2_000_000.0, "s", "T30:2"),  # 1000× the unit of FX/PPP
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2018", 250.0, "s"))  # ILOSTAT's own (correct) USD figure
    u = build.UnitGraph(s, DIC, ["2018"], META)
    assert not u.year("AAA", "2018").linked("ilo:ilo_monthly_mean@X:1")
    assert build.ilo_variants(s, u, "AAA", "2018", DIC) == []
    u.explain("AAA", "2018", True)
    assert any(e["scope"] == "wage:ilo_monthly_mean" for e in u.log)


def test_units_ilostat_notes_set_concept_and_exclude_real_values():
    s = _store(*_wdi("AAA", "2019", 10.0, 5.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2019", 3800.0, "s", "T8:128 T9:133 S4:31"),
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2019", 380.0, "s"),
               Obs("ilo_hourly_mean@X:2", "AAA", "2019", 20.0, "s", "T8:127 T9:131"),
               Obs("ilo_hourly_mean_usd@X:2", "AAA", "2019", 2.0, "s"))
    u = build.UnitGraph(s, DIC, ["2019"], META)
    vs = build.ilo_variants(s, u, "AAA", "2019", DIC)
    assert [(v.key, v.restricted) for v in vs] == [("ilo_median_monthly", True)]  # median per its note; real-value record dropped
    assert any("Urban areas only" in t for t in _texts(vs[0].caveat))


def test_units_oecd_wage_joined_by_its_ppp_identity():
    s = _store(*_wdi("AAA", "2025", 0.9, 0.7),
               Obs("oecd_avg_annual_wage", "AAA", "2025", 50000.0, "s", "EUR"),
               Obs("oecd_avg_annual_wage_q", "AAA", "2025", 50000.0, "s", "EUR 2025"),
               Obs("oecd_avg_annual_wage_q_usdppp", "AAA", "2025", 50000.0 / 0.7, "s", "USD_PPP 2025"),
               # a second economy whose OECD series is in another unit than WDI's LCU series
               *[Obs(*o) for o in _wdi("BBB", "2025", 1.8, 0.39, lcu_unit_fx=0.92)],
               Obs("oecd_avg_annual_wage", "BBB", "2025", 28000.0, "s", "BGN"))
    u = build.UnitGraph(s, DIC, ["2025"], META)
    assert build.oecd_variant(s, u, "AAA", "2025") is not None
    assert build.oecd_variant(s, u, "BBB", "2025") is None


def test_units_physically_impossible_hours_drop_both_records():
    # ILOSTAT ZAF 2017 (same source): median monthly 3500, median hourly 0.102 -> 34,000 hours a month.
    s = _store(*_wdi("AAA", "2017", 13.3, 6.0),
               Obs("ilo_monthly_mean@BA:1", "AAA", "2017", 3500.0, "s", "T8:128 T9:133"),
               Obs("ilo_monthly_mean_usd@BA:1", "AAA", "2017", 263.0, "s"),
               Obs("ilo_hourly_mean@BA:1", "AAA", "2017", 0.102, "s", "T8:128 T9:133"),
               Obs("ilo_hourly_mean_usd@BA:1", "AAA", "2017", 0.0077, "s"))
    u = build.UnitGraph(s, DIC, ["2017"], META)
    assert build.ilo_variants(s, u, "AAA", "2017", DIC) == []


def test_units_wage_matching_both_factors_does_not_join_them():
    # Dollarisation year: WDI's LCU series is in US$, the official rate still in colones (×8.75);
    # ILOSTAT converted its wage with both, so it "agrees" with each - that proves nothing.
    s = _store(*_wdi("AAA", "2000", 8.75, 0.5, lcu_unit_fx=1.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2000", 3000.0, "s", "T8:127 T9:133"),
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2000", 3000.0 / 8.75, "s"),
               Obs("ilo_monthly_mean_ppp@X:1", "AAA", "2000", 3000.0 / 0.5, "s"))
    u = build.UnitGraph(s, DIC, ["2000"], META)
    g = u.year("AAA", "2000")
    assert g.linked("P") and not g.linked("F") and not g.linked("ilo:ilo_monthly_mean@X:1")
    u.explain("AAA", "2000", True)
    assert any("d.ilo.ambiguous" in _keys(e["detail"]) for e in u.log)


def test_units_ppp_proven_by_icp_price_level_and_carried_both_ways():
    # No household-consumption totals in WDI: the PPP is checked in 2021 against ICP's price
    # level (US = 1) × the official rate, and carried to adjacent years that moved < ×1.4.
    rows = []
    for y, fx, ppp in (("2020", 150.0, 140.0), ("2021", 155.0, 155.7), ("2022", 160.0, 171.4), ("2023", 400.0, 205.2)):
        rows += [("fx_lcu_usd", "AAA", y, fx, "s"), ("ppp_hfce", "AAA", y, ppp, "s"),
                 ("gdp_lcu", "AAA", y, fx * 1000, "s"), ("gdp_usd", "AAA", y, 1000.0, "s")]
    s = _store(*rows, ("icp21_pli_wl_hfce", "AAA", "2021", 50.0, "s", "A"),
               ("icp21_pli_wl_hfce", "USA", "2021", 49.8, "s", "United States"))
    u = build.UnitGraph(s, DIC, ["2020", "2021", "2022", "2023"], META)
    assert [u.year("AAA", y).linked("P") for y in ("2020", "2021", "2022", "2023")] == [True, True, True, True]
    s = _store(*rows, ("icp21_pli_wl_hfce", "AAA", "2021", 5.0, "s", "A"),  # PPP 10× the ICP price level
               ("icp21_pli_wl_hfce", "USA", "2021", 49.8, "s", "United States"))
    u = build.UnitGraph(s, DIC, ["2020", "2021", "2022", "2023"], META)
    assert not any(u.year("AAA", y).linked("P") for y in ("2020", "2021", "2022", "2023"))


def test_units_time_check_only_among_same_currency_figures():
    # A monthly figure published in another currency (×100) is left out for its currency,
    # and must not knock out the hourly figure it would contradict.
    s = _store(*_wdi("AAA", "2018", 100.0, 80.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2018", 3000.0, "s", "T8:127 T9:133"),  # in another currency
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2018", 3500.0, "s"),
               Obs("ilo_hourly_mean@X:2", "AAA", "2018", 1800.0, "s", "T8:127 T9:133"),
               Obs("ilo_hourly_mean_usd@X:2", "AAA", "2018", 18.0, "s"),
               Obs("ilo_weekly_hours@X:2", "AAA", "2018", 38.0, "s"))
    u = build.UnitGraph(s, DIC, ["2018"], META)
    assert [v.key for v in build.ilo_variants(s, u, "AAA", "2018", DIC)] == ["ilo_mean_hourly"]
    # Same currency, but the hourly figure is 100× too small against OECD's wage and hours.
    s = _store(*_wdi("AAA", "2018", 100.0, 80.0),
               Obs("ilo_hourly_mean@X:2", "AAA", "2018", 18.0, "s", "T8:127 T9:133"),
               Obs("ilo_hourly_mean_usd@X:2", "AAA", "2018", 0.18, "s"),
               Obs("oecd_avg_annual_wage", "AAA", "2018", 3_600_000.0, "s", "AAD"),
               Obs("oecd_avg_annual_wage_q", "AAA", "2018", 3_600_000.0, "s", "AAD 2018"),
               Obs("oecd_avg_annual_wage_q_usdppp", "AAA", "2018", 45000.0, "s", "USD_PPP 2018"),
               Obs("oecd_usual_weekly_hours_ft", "AAA", "2018", 40.0, "s"))
    u = build.UnitGraph(s, DIC, ["2018"], META)
    assert build.ilo_variants(s, u, "AAA", "2018", DIC) == []
    assert build.oecd_variant(s, u, "AAA", "2018") is not None


def _per_head(area, years, ppp, per_head):
    """Population giving the stated household consumption per head with _wdi's totals."""
    return [("population", area, y, ppp * 500 / v, "s") for y, v in zip(years, per_head)]


def _oecd_yardstick(area, years, wages, per_head):
    """An OECD average-wage series and the household consumption per head it is set
    against, from which the level bounds are derived."""
    rows = [r for y in years for r in _wdi(area, y, 1.0, 1.0)] + _per_head(area, years, 1.0, per_head)
    return rows + [Obs("oecd_avg_annual_wage", area, y, w, "s", "OOD") for y, w in zip(years, wages)]


def test_units_scale_error_singled_out_by_its_own_series():
    # PRY BX:14043 2020: the hourly figure is 1/192 of its neighbours, the monthly one is in line.
    years = ["2019", "2020", "2021"]
    rows = [r for y in years for r in _wdi("AAA", y, 6000.0, 2500.0)] + _per_head("AAA", years, 2500.0, [100.0, 103.0, 113.0])
    obs = []
    for y, m, h in (("2019", 2_489_188.0, 15079.0), ("2020", 2_505_151.0, 78.482), ("2021", 2_584_029.0, 16570.0)):
        obs += [Obs("ilo_monthly_mean@X:1", "AAA", y, m, "s", "T8:127 T9:133"), Obs("ilo_monthly_mean_usd@X:1", "AAA", y, m / 6000, "s"),
                Obs("ilo_hourly_mean@X:1", "AAA", y, h, "s", "T8:127 T9:133"), Obs("ilo_hourly_mean_usd@X:1", "AAA", y, h / 6000, "s")]
    s = _store(*rows, *obs)
    u = build.UnitGraph(s, DIC, years, META)
    assert [v.key for v in build.ilo_variants(s, u, "AAA", "2020", DIC)] == ["ilo_mean_monthly"]
    assert [v.key for v in build.ilo_variants(s, u, "AAA", "2021", DIC)] == ["ilo_mean_hourly", "ilo_mean_monthly"]


def test_history_breaks_at_level_shift_and_primary_switch_is_marked():
    years = ["2021", "2022", "2023", "2024"]
    rows = [r for y in years for r in _wdi("AAA", y, 1.0, 0.8)] + _per_head("AAA", years, 0.8, [100.0, 105.0, 110.0, 116.0])
    obs = []
    for y, m in zip(years, (1000.0, 1050.0, 1100.0, 1900.0)):  # 2023->2024: ×1.73 against ×1.05
        obs += [Obs("ilo_monthly_mean@X:1", "AAA", y, m, "s", "T8:127 T9:133"), Obs("ilo_monthly_mean_usd@X:1", "AAA", y, m, "s")]
    # OECD's own series moved at most ×1.10 a year against consumption per head.
    oecd = _oecd_yardstick("OOO", years, [100.0, 115.5, 121.0, 127.6], [100.0, 105.0, 110.0, 116.0])
    s = _store(*rows, *obs, *oecd, Obs("gold_usd_oz", "WLD", "2021-01", 1800.0, "s"))
    u = build.UnitGraph(s, DIC, years, META)
    assert abs(u.level_bound("hfce_lcu", 1) - 1.10) < 1e-9 and abs(u.level_bound("hfce_lcu", 5) - 1.10) < 1e-9
    gold = {"annual": {y: {"usd_g": 60.0} for y in years}}
    meta = {"AAA": {"is_economy": True, "name_en": "A"}}
    pts = build.wage_gold_history(s, gold, meta, DIC, u)["AAA"]["points"]
    assert [p[4] for p in pts] == [False, False, False, True] and pts[3][5]["k"] == "d.hist.shift"
    assert [round(x["bound"], 2) for x in _params(pts[3][5], "d.shift.vs_bound")] == [1.10, 1.10]
    caveat = build.ilo_variants(s, u, "AAA", "2024", DIC)[0].caveat
    assert caveat[0]["k"] == "d.cav.shift" and [(x["n"], round(x["bound"], 2)) for x in _params(caveat[0], "d.shift.vs_bound")] == [(1, 1.10)] * 2
    w = lambda sid, key, notes, label: {"role": None, "mrole": "primary", "series_id": sid, "series_key": key,  # noqa: E731
                                        "notes_sig": notes, "label": label, "restricted": False, "source": "x"}
    recs = {"2022": {"wages": [w("A", "A", [], "a")]}, "2023": {"wages": [w("A n1", "A", ["n1"], "a")]},
            "2024": {"wages": [w("B", "B", [], "b")]}}
    build.mark_switches(recs)
    assert recs["2023"]["wages"][0]["mrole_switch"] == {"year": "2022", "label": "a", "restricted": False, "source": "x", "kind": "notes",
                                                        "only_before": [], "only_now": ["n1"]}
    assert recs["2024"]["wages"][0]["mrole_switch"]["kind"] == "source"


def test_units_concept_gap_is_not_a_time_unit_error():
    # MEX 2001: an LFS mean monthly wage is 0.44 of OECD's full-time-equivalent wage and
    # no other figure exists that year - a difference of concept, not of time unit.
    s = _store(*_wdi("AAA", "2001", 9.34, 6.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2001", 3320.05, "s", "T8:127 T9:133"),
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2001", 355.4, "s"),
               Obs("oecd_avg_annual_wage", "AAA", "2001", 91411.8, "s", "AAD"),
               Obs("oecd_avg_annual_wage_q", "AAA", "2001", 91411.8, "s", "AAD 2001"),
               Obs("oecd_avg_annual_wage_q_usdppp", "AAA", "2001", 91411.8 / 6.0, "s", "USD_PPP 2001"),
               Obs("oecd_usual_weekly_hours_ft", "AAA", "2001", 47.5, "s"))
    u = build.UnitGraph(s, DIC, ["2001"], META)
    assert [v.key for v in build.ilo_variants(s, u, "AAA", "2001", DIC)] == ["ilo_mean_monthly"]


def test_units_hours_with_scale_error_are_not_used():
    # BLR BA:13362: 39 hours a week for years, then 3.89 - not used to derive an hourly wage.
    years = ["2023", "2024", "2025"]
    rows = [r for y in years for r in _wdi("AAA", y, 3.0, 1.2)]
    obs = [Obs("ilo_weekly_hours@X:1", "AAA", y, h, "s") for y, h in zip(years, (39.2, 39.3, 3.89))]
    obs += [Obs("ilo_monthly_mean@X:1", "AAA", "2025", 2000.0, "s", "T8:127 T9:133"),
            Obs("ilo_monthly_mean_usd@X:1", "AAA", "2025", 2000.0 / 3.0, "s")]
    s = _store(*rows, *obs)
    u = build.UnitGraph(s, DIC, years, META)
    v = build.ilo_variants(s, u, "AAA", "2025", DIC)[0]
    assert v.hourly_lcu is None and any(e["scope"] == "hours" and e["year"] == "2025" for e in u.log)


def test_restricts_reads_coverage_labels():
    assert not build.restricts("S4", "Geographical coverage: Total national")
    assert build.restricts("S4", "Geographical coverage: Total national, excluding some areas")
    assert not build.restricts("S4", "Geographical coverage: Total national, excluding overseas territories")
    assert build.restricts("S4", "Geographical coverage: Urban areas only")
    assert not build.restricts("S4", "Geographical coverage: Not applicable")
    assert build.restricts("T3", "Age coverage - maximum age: 64 years old")
    assert "T2" not in build.COVERAGE_NOTES  # a minimum (working) age limits no one's coverage
    assert not build.restricts("T12", "Working time arrangement coverage: Full-time equivalents")
    assert not build.restricts("T12", "Working time arrangement coverage: Full-time and part time workers")
    assert build.restricts("T12", "Working time arrangement coverage: Full-time workers")
    assert not build.restricts("S9", "Reference group coverage: Total employment")
    assert build.restricts("S9", "Reference group coverage: Insured persons")
    assert not build.restricts("S5", "Population coverage: Excluding both institutional population and armed forces and/or conscripts")
    assert build.restricts("S5", "Population coverage: Nationals only")
    assert build.restricts("S6", "Establishment size coverage: All establishments with at least 50 employees")
    assert not build.restricts("S6", "Establishment size coverage: All establishments with at least 50 employees "
                                     "and a sample of those with less than 50 employees")


def test_median_shown_only_from_the_primary_source():
    # Coverage first: OECD's full-coverage wage leads over an ILOSTAT mean with limited
    # coverage, and a median of another source is not drawn next to it.
    wages = [{"key": "oecd_fte", "restricted": False, "hourly_lcu": 10.0, "monthly_lcu": 1700.0, "source_id": "OECD",
              "role": None, "mrole": None},
             {"key": "ilo_median_monthly", "restricted": False, "hourly_lcu": None, "monthly_lcu": 1500.0,
              "source_id": "ILOSTAT X:1", "role": None, "mrole": None},
             {"key": "ilo_mean_monthly", "restricted": True, "hourly_lcu": None, "monthly_lcu": 1800.0,
              "source_id": "ILOSTAT X:1", "role": None, "mrole": None}]
    build.mark_roles(wages)
    assert [w["mrole"] for w in wages] == ["primary", None, None]
    # An ILOSTAT mean covering all employees leads over OECD; its own survey's median is drawn with it.
    wages[2]["restricted"] = False
    for w in wages:
        w["mrole"] = w["role"] = None
    build.mark_roles(wages)
    assert [w["mrole"] for w in wages] == [None, "typical", "primary"]


def test_prove_identity_failure_next_to_a_proven_year_is_unknown():
    # GUY 2005: the PPP identity fails (×2.5) although the PPP moved ×1.03 from a proven year.
    years = ["2005", "2006"]
    s = _store(("ppp_hfce", "AAA", "2005", 95.94, "s"), ("hfce_lcu", "AAA", "2005", 38.4 * 500, "s"),
               ("hfce_intl", "AAA", "2005", 500.0, "s"), ("ppp_hfce", "AAA", "2006", 99.15, "s"),
               ("hfce_lcu", "AAA", "2006", 99.15 * 500, "s"), ("hfce_intl", "AAA", "2006", 500.0, "s"))
    u = build.UnitGraph(s, DIC, years, META)
    _f, p, _h = u._factors("AAA")
    assert p["2006"][0] is True and p["2005"][0] is None and p["2005"][2] == "identity"
    assert "d.prove.chain" in _keys(p["2005"][1]) and "d.ppp.failed" not in _keys(p["2005"][1])


def test_cross_source_gap_between_time_factor_and_week_month_is_kept_unconfirmed():
    def variants(b_value):
        s = _store(*_wdi("AAA", "2018", 10.0, 8.0),
                   Obs("ilo_monthly_mean@X:1", "AAA", "2018", 1000.0, "s", "T8:127 T9:133"),
                   Obs("ilo_monthly_mean_usd@X:1", "AAA", "2018", 100.0, "s"),
                   Obs("ilo_monthly_mean@Y:2", "AAA", "2018", b_value, "s", "T8:127 T9:133"),
                   Obs("ilo_monthly_mean_usd@Y:2", "AAA", "2018", b_value / 10, "s"),
                   ("population", "AAA", "2018", 1e6, "s"))
        u = build.UnitGraph(s, DIC, ["2018"], META)
        return build.ilo_variants(s, u, "AAA", "2018", DIC), u
    # ×3: a concept gap or a time-unit error - kept, said to be unconfirmed.
    vs, _u = variants(3000.0)
    assert len(vs) == 1 and "d.tu.unsure" in _keys(vs[0].caveat)
    # ×4.4 (a week-month factor) with nothing else to decide: neither is used.
    vs, u = variants(4400.0)
    u.explain("AAA", "2018", True)
    assert vs == [] and sum("d.tu.verdict_undecided" in _keys(e["detail"]) for e in u.log) == 2


def test_oecd_vs_survey_summary():
    def row(o, i):
        return {"wages": [{"key": "oecd_fte", "monthly_lcu": o}, {"key": "ilo_mean_monthly", "monthly_lcu": i}]}
    countries = {"AAA": {"years": {"2020": row(100.0, 80.0), "2021": row(100.0, 120.0)}},
                 "BBB": {"years": {"2020": row(200.0, 100.0), "2021": {"wages": [{"key": "oecd_fte", "monthly_lcu": 1.0}]}}}}
    s = build.oecd_vs_survey(countries)
    assert s["n"] == 3 and s["min"] == 0.5 and s["max"] == 1.2 and s["min_at"] == ["BBB", "2020"]
    assert s["median"] == 0.8 and abs(s["below"] - 2 / 3) < 1e-12
    countries["CCC"] = {"years": {"2020": row(100.0, 90.0)}}
    assert build.oecd_vs_survey(countries)["median"] == (0.8 + 0.9) / 2  # even count: mean of the middle two


def test_series_continued_with_its_publishers_release():
    # ILOSTAT republishes X:1 to 2021; the publisher's own release has 2020-2023.
    rows = []
    for y, v in (("2019", 1000.0), ("2020", 1050.0), ("2021", 1100.0)):
        rows += [Obs("ilo_monthly_mean@X:1", "AAA", y, v, "s", "T8:127 T9:133 T30:1"),
                 Obs("ilo_monthly_mean_usd@X:1", "AAA", y, v / 2.0, "s")]
    ext = [Obs("ext_ilo_monthly_mean@X:1", "AAA", y, v, "p", "pub") for y, v in
           (("2020", 1050.0), ("2021", 1101.0), ("2022", 1150.0), ("2023", 5000.0))]
    wdi = [r for y in ("2019", "2020", "2021", "2022", "2023") for r in _wdi("AAA", y, 2.0, 1.0)]
    years = ["2019", "2020", "2021", "2022", "2023"]
    u = build.UnitGraph(_store(*wdi, *rows, *ext), DIC, years, META)
    recs = u.area("AAA")["ilo"]
    r22 = next(r for r in recs["2022"] if r.series == "ilo_monthly_mean@X:1")
    assert r22.publisher == "pub" and r22.obs.value == 1150.0 and r22.match["k"] == "d.ext.match"
    assert u.year("AAA", "2022").linked("ilo:ilo_monthly_mean@X:1")  # carried from 2021 (×1.045)
    assert not u.year("AAA", "2023").linked("ilo:ilo_monthly_mean@X:1")  # ×4.3 from 2022: unit not carried
    assert all(r.publisher is None for r in recs["2021"])  # ILOSTAT's own years stay ILOSTAT's
    # Continued years are described by the series' concept notes, not by notes about
    # ILOSTAT's latest year itself (here a break in series and a remark on 2021).
    noted = [Obs(o.series, o.area, o.period, o.value, o.snapshot, o.note + (" I11:264 I13:280" if o.period == "2021" and "@" in o.series and "_usd" not in o.series else ""))
             for o in rows]
    u3 = build.UnitGraph(_store(*wdi, *noted, *ext), DIC, years, META)
    r22 = next(r for r in u3.area("AAA")["ilo"]["2022"] if r.series == "ilo_monthly_mean@X:1")
    r21 = next(r for r in u3.area("AAA")["ilo"]["2021"] if r.series == "ilo_monthly_mean@X:1")
    assert r21.break_in_series and not r22.break_in_series
    assert "I13:280" not in r22.obs.note and "T8:127" in r22.obs.note and r22.signature == r21.signature
    # A release that disagrees with ILOSTAT on a common year continues nothing.
    bad = [Obs("ext_ilo_monthly_mean@X:1", "AAA", y, v, "p", "pub") for y, v in (("2021", 1200.0), ("2022", 1250.0))]
    u2 = build.UnitGraph(_store(*wdi, *rows, *bad), DIC, years, META)
    assert not u2.area("AAA")["ilo"].get("2022")
    assert any(e["detail"]["k"] == "d.ext.disagree" for e in u2.log)


def _icp(code: str, **cn) -> list:
    return [Obs(f"icp21_cn_{k}", code, "2021", v, "icp", "Testland") for k, v in cn.items()]


ICP_OK = dict(food_nonalc=20, alcohol_tobacco=3, clothing=5, housing=25, furnishings=5, health=12, transport=10,
              communication=3, recreation=6, education=8, restaurants_hotels=4, misc=9, net_purchases_abroad=-10,
              hfce=80, hfce_no_housing=65, gov_individual=20, aic=100)


def test_icp_composition_adds_up_rent_and_other():
    from wagegold import living
    log = []
    sp = living.icp_spending(_store(*_icp("AAA", **ICP_OK)), "AAA", lambda d, k: log.append((d, k)))
    assert not log
    # Rent = 80 - 65 = 15; domestic consumption without rent = 65 - (-10) = 75; the five
    # other named groups 43, so other = 32 (of 80), of which 7 itemised.
    assert abs(sp["shares"]["rent"] - 15 / 80) < 1e-12 and abs(sp["shares"]["other"] - 32 / 80) < 1e-12
    assert abs(sp["other_parts"]["rest"] - 25 / 80) < 1e-12 and abs(sp["housing_actual"] - 25 / 80) < 1e-12
    assert abs(sum(sp["shares"].values()) + sp["net_abroad"] - 1) < 1e-12
    assert abs(sum(sp["other_parts"].values()) - sp["shares"]["other"]) < 1e-12
    assert abs(sp["government"] - 20 / 80) < 1e-12 and sp["net_abroad_published"]


def test_icp_unpublished_net_purchases_abroad_is_zero_and_still_checked():
    from wagegold import living
    log = []
    # Not published, and the other parts add up to AIC on their own: taken as zero.
    ok = {**{k: v for k, v in ICP_OK.items() if k != "net_purchases_abroad"}, "aic": 110, "hfce": 90, "hfce_no_housing": 75}
    sp = living.icp_spending(_store(*_icp("AAA", **ok)), "AAA", lambda d, k: log.append(k))
    assert sp and not sp["net_abroad_published"] and sp["net_abroad"] == 0 and not log
    # Not published, and the parts do not add up: the identity is not made to hold.
    bad = {k: v for k, v in ICP_OK.items() if k != "net_purchases_abroad"}
    assert living.icp_spending(_store(*_icp("AAA", **bad)), "AAA", lambda d, k: log.append(k)) is None
    assert log == ["icp"]


def test_icp_composition_failing_a_check_is_left_out():
    from wagegold import living
    cases = {
        "identity": {**ICP_OK, "gov_individual": 30},  # 80 + 30 != 100
        "rent beyond actual housing": {**ICP_OK, "hfce_no_housing": 50},  # rent 30 > housing 25
        # restaurants 30 + alcohol 3 > other 32 (health, recreation and education moved to restaurants)
        "itemised parts beyond other": {**ICP_OK, "restaurants_hotels": 30, "health": 0, "recreation": 0, "education": 0},
        "missing": {k: v for k, v in ICP_OK.items() if k != "hfce_no_housing"},
    }
    for name, cn in cases.items():
        log = []
        assert living.icp_spending(_store(*_icp("AAA", **cn)), "AAA", lambda d, k: log.append(k)) is None, name
        assert log == (["missing"] if name == "missing" else ["icp"]), (name, log)


def test_icp_revision_decides_the_currency_unit_by_both_ratios():
    from wagegold import living
    base = [*_icp("AAA", icp21_dummy=1), Obs("icp21_pli_wl_hfce", "USA", "2021", 150.0, "icp")]

    def rev(icp_ppp, wdi_ppp, icp_pli, gdp_factor, icp_hfce, wdi_hfce):
        rows = [*base, Obs("icp21_ppp_hfce", "AAA", "2021", icp_ppp, "icp"), Obs("icp21_pli_wl_hfce", "AAA", "2021", icp_pli, "icp"),
                Obs("hfce_lcu", "AAA", "2021", wdi_hfce, "w"), Obs("gdp_lcu", "AAA", "2021", gdp_factor * 1e6, "w"),
                Obs("gdp_usd", "AAA", "2021", 1e6, "w")]
        if wdi_ppp:
            rows.append(Obs("ppp_hfce", "AAA", "2021", wdi_ppp, "w"))
        return living.revision(_store(*rows), "AAA", "AAA", icp_hfce, 1.4)
    # Same currency, PPP revised by 8% since ICP: the revision is the totals' ratio.
    r = rev(10.0, 10.8, 100.0, 15.0, 93.0, 100e9)  # ICP exchange rate 10 × 150 / 100 = 15 = WDI's
    assert abs(r["revision"] - 0.93) < 1e-12 and r["converted"] is None
    # Redenominated 1000:1 since ICP: converted at the exchange-rate ratio.
    r = rev(10000.0, 10.3, 100.0, 15.0, 100e3, 100e9)
    assert abs(r["converted"] - 1000) < 1e-9 and r["by"] == "fx" and abs(r["revision"] - 1.0) < 1e-12
    # The two ratios disagree (one says same unit, the other not): unknown.
    assert rev(10000.0, 9000.0, 100.0, 15.0, 100e3, 100e9)["revision"] is None
    # No PPP of WDI: only the exchange-rate ratio decides.
    assert rev(10.0, None, 100.0, 15.0, 120.0, 100e9)["revision"] == 1.2


def test_consumption_needs_its_currency_unit_proven():
    # The PPP identity proves household consumption (H); a year whose identity fails is
    # left out; under high inflation H is carried by its share of GDP when the exchange
    # rate's identity puts GDP in the same unit both years.
    years = ["2020", "2021", "2022"]
    rows = []
    for y, hf, hi, ppp, gdp, fx in (("2020", 600.0, 100.0, 6.0, 1000.0, 10.0), ("2021", 1200.0, 100.0, 30.0, 2000.0, 20.0),
                                    ("2022", 2400.0, None, None, 4000.0, 40.0)):
        rows += [Obs("hfce_lcu", "AAA", y, hf, "w"), Obs("gdp_lcu", "AAA", y, gdp, "w"), Obs("gdp_usd", "AAA", y, 100.0, "w"),
                 Obs("fx_lcu_usd", "AAA", y, fx, "w"), Obs("population", "AAA", y, 10.0, "w")]
        if hi:
            rows.append(Obs("hfce_intl", "AAA", y, hi, "w"))
        if ppp:
            rows.append(Obs("ppp_hfce", "AAA", y, ppp, "w"))
    u = build.UnitGraph(_store(*rows), DIC, years, META)
    assert u.year("AAA", "2020").linked("H")  # 600 / 100 = 6 = PPP
    assert not u.year("AAA", "2021").linked("H")  # 1200 / 100 = 12 vs PPP 30: beyond ×/÷1.4
    cons, _s, why = u.consumption("AAA", "2021")
    assert cons is None and why is not None
    # 2022: no PPP; its value doubled from 2021 (not proven anyway) - nothing to carry from.
    assert not u.year("AAA", "2022").linked("H")


def test_consumption_carried_by_share_of_gdp():
    years = ["2021", "2022"]
    rows = []
    for y, hf, hi, ppp, gdp in (("2021", 600.0, 100.0, 6.0, 1000.0), ("2022", 1800.0, None, None, 3000.0)):
        rows += [Obs("hfce_lcu", "AAA", y, hf, "w"), Obs("gdp_lcu", "AAA", y, gdp, "w"), Obs("gdp_usd", "AAA", y, 100.0, "w"),
                 Obs("fx_lcu_usd", "AAA", y, gdp / 100.0, "w"), Obs("population", "AAA", y, 10.0, "w")]
        if hi:
            rows += [Obs("hfce_intl", "AAA", y, hi, "w"), Obs("ppp_hfce", "AAA", y, ppp, "w")]
    u = build.UnitGraph(_store(*rows), DIC, years, META)
    # ×3 in a year (beyond ×/÷1.4), but the share of GDP is 0.6 both years.
    assert u.year("AAA", "2022").linked("H") and u.consumption("AAA", "2022")[0] == 1800.0 / 10 / 12


def test_residents_per_employed_and_bounds():
    from wagegold import living
    s = _store(Obs("population", "AAA", "2021", 1000, "p"), Obs("population_0_14", "AAA", "2021", 200, "p"),
               Obs("emp_to_pop_15plus", "AAA", "2021", 50, "e"), Obs("employees_pct_emp", "AAA", "2021", 80, "e"))
    log = []
    c = living.context(s, "AAA", "2021", lambda y, d: log.append(d))
    assert abs(c["residents_per_employed"] - 1000 / 400) < 1e-12 and c["employees_share"] == 0.8 and not log
    s2 = _store(Obs("population", "AAA", "2021", 1000, "p"), Obs("population_0_14", "AAA", "2021", 200, "p"),
                Obs("emp_to_pop_15plus", "AAA", "2021", 150, "e"))
    assert living.context(s2, "AAA", "2021", lambda y, d: log.append(d))["residents_per_employed"] is None
    assert log[-1]["k"] == "d.liv.ctx_emp"
    s3 = _store(Obs("population", "AAA", "2021", 1000, "p"), Obs("population_0_14", "AAA", "2021", 1000, "p"),
                Obs("emp_to_pop_15plus", "AAA", "2021", 50, "e"))
    assert living.context(s3, "AAA", "2021", lambda y, d: log.append(d))["residents_per_employed"] is None
    assert log[-1]["k"] == "d.liv.ctx_pop"
