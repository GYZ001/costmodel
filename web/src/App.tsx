import { useMemo, useState } from "react";
import type { Dataset } from "./types";
import { bestYear, countryName, fmt, wageYears, type View } from "./lib";
import { ChainSection } from "./sections/Chain";
import { GoldPerHour } from "./sections/GoldPerHour";
import { GoldBuys } from "./sections/GoldBuys";
import { RealWage } from "./sections/RealWage";
import { PriceStructure } from "./sections/PriceStructure";
import { GoldRuler } from "./sections/GoldRuler";
import { ChinaUs } from "./sections/ChinaUs";
import { Claims } from "./sections/Claims";
import { Methods } from "./sections/Methods";

export type Group = "g20" | "all";

export interface Scope {
  ds: Dataset;
  year: string;
  view: View;
  group: Group;
  picks: string[];
  /** Each picked economy keeps the categorical colour slot it was given when picked (0–7). */
  slotOf: Record<string, number>;
  togglePick: (iso3: string) => void;
}

const DEFAULT_PICKS = ["CHN", "USA", "JPN", "DEU", "IND", "BRA"];
const MAX_PICKS = 8; // one per categorical series colour

interface Pick { iso: string; slot: number }

function toggle(cur: Pick[], iso: string): Pick[] {
  if (cur.some((p) => p.iso === iso)) return cur.filter((p) => p.iso !== iso);
  const kept = cur.length >= MAX_PICKS ? cur.slice(1) : cur;
  const used = new Set(kept.map((p) => p.slot));
  const slot = [...Array(MAX_PICKS).keys()].find((i) => !used.has(i))!;
  return [...kept, { iso, slot }];
}

export default function App({ ds }: { ds: Dataset }) {
  const [view, setView] = useState<View>("hourly");
  const best = useMemo(() => bestYear(ds, view), [ds, view]);
  const [yearPick, setYearPick] = useState<string | null>(null);
  const year = yearPick ?? best;
  const [group, setGroup] = useState<Group>("g20");
  const [picked, setPicked] = useState<Pick[]>(() => DEFAULT_PICKS.filter((c) => ds.countries[c]).reduce(toggle, [] as Pick[]));
  const togglePick = (iso3: string) => setPicked((cur) => toggle(cur, iso3));
  const picks = useMemo(() => picked.map((p) => p.iso), [picked]);
  const slotOf = useMemo(() => Object.fromEntries(picked.map((p) => [p.iso, p.slot])), [picked]);

  const years = useMemo(() => {
    const ys = new Set<string>();
    for (const c of Object.values(ds.countries)) for (const y of wageYears(c, view)) if (y >= "2015") ys.add(y);
    return [...ys].sort().reverse();
  }, [ds, view]);

  const scope: Scope = { ds, year, view, group, picks, slotOf, togglePick };
  const missing = useMemo(
    () =>
      Object.entries(ds.countries)
        .filter(([iso, c]) => (group === "all" ? picks.includes(iso) : c.g20 || picks.includes(iso)))
        .filter(([, c]) => !wageYears(c, view).includes(year))
        .map(([, c]) => {
          const ys = wageYears(c, view);
          if (view === "hourly" && wageYears(c, "monthly").includes(year)) return `${countryName(c)}（该年无同口径时薪，可切换“按月薪”）`;
          return `${countryName(c)}${ys.length ? `（最近 ${ys[0]} 年）` : "（无可核对数据）"}`;
        }),
    [ds, group, picks, view, year],
  );
  const passed = ds.checks.filter((c) => c.status === "pass").length;
  const failed = ds.checks.filter((c) => c.status === "fail").length;
  const g = ds.gold.latest;

  return (
    <>
      <header className="top wrap">
        <h1>一小时的劳动，能换多少黄金、买多少东西？</h1>
        <p className="lede">
          把各国的时薪先换成<strong>黄金克数</strong>，再看这些黄金在<strong>当地</strong>能买到多少东西。
          全部数字来自世界银行、国际劳工组织、OECD、美国劳工统计局、国家统计局等官方发布，原始文件逐个存档、可追溯、可复算。
        </p>
        <div className="toolbar">
          <span className="badge">
            <span className="dot" style={{ background: "var(--gold)" }} />
            最新金价 {g.period}：{fmt(g.usd_oz, 0)} 美元/盎司 ≈ {fmt(g.usd_g, 1)} 美元/克
          </span>
          <span className="badge">
            <span className="dot" style={{ background: failed ? "var(--critical)" : "var(--good)" }} />
            交叉校验 {passed}/{ds.checks.length} 通过
          </span>
          <span className="badge">数据生成于 {new Date(ds.generated_at).toLocaleString("zh-CN", { hour12: false })}</span>
          {ds.stale.length > 0 && <span className="badge">⚠ {ds.stale.length} 个来源本次未更新，沿用上次快照</span>}
        </div>
      </header>

      <nav className="sections" aria-label="章节">
        <div className="wrap">
          <a href="#chain">三步换算</a>
          <a href="#gold">劳动→黄金</a>
          <a href="#buys">黄金→商品</a>
          <a href="#real">真实购买力</a>
          <a href="#structure">什么贵什么便宜</a>
          <a href="#ruler">黄金这把尺子</a>
          <a href="#cnus">中美细看</a>
          <a href="#claims">核对之前的说法</a>
          <a href="#method">方法与来源</a>
        </div>
      </nav>

      <main className="wrap">
        <section className="block" aria-label="全局筛选">
          <div className="controls" style={{ marginBottom: 0 }}>
            <span className="seg" role="group" aria-label="工资口径">
              <button aria-pressed={view === "hourly"} onClick={() => setView("hourly")}>按时薪</button>
              <button aria-pressed={view === "monthly"} onClick={() => setView("monthly")}>按月薪（不需工时假设）</button>
            </span>
            <label>
              参考年份{" "}
              <select value={year} onChange={(e) => setYearPick(e.target.value)} title="默认年份：至少三分之二的 G20 成员有数据的最近年份">
                {years.map((y) => (
                  <option key={y} value={y}>
                    {y} 年{y === best ? "（默认）" : ""}
                  </option>
                ))}
              </select>
            </label>
            <span className="seg" role="group" aria-label="经济体范围">
              <button aria-pressed={group === "g20"} onClick={() => setGroup("g20")}>二十国集团（G20）成员</button>
              <button aria-pressed={group === "all"} onClick={() => setGroup("all")}>全部有数据的经济体</button>
            </span>
          </div>
          <div className="controls" style={{ marginTop: 10 }}>
            <span>重点对比：</span>
            <div className="chips">
              {picks.map((iso) => (
                <button key={iso} className="chip" aria-pressed="true" onClick={() => togglePick(iso)} title="点击移除">
                  {countryName(ds.countries[iso])} <span className="x">×</span>
                </button>
              ))}
              <AddCountry ds={ds} picks={picks} onAdd={togglePick} />
            </div>
          </div>
          <p className="small muted" style={{ margin: "8px 0 0" }}>
            所有经济体都用同一参考年份的工资、该年平均汇率、该年平均金价和该年物价——金价几年内能翻倍，混用年份会让“克金工资”失真。
            默认年份是至少三分之二的 G20 成员有数据的最近年份（{best} 年）。
            {missing.length > 0 && <> 该年缺少可核对工资数据：{missing.join("、")}。</>}
          </p>
        </section>

        <ChainSection {...scope} />
        <GoldPerHour {...scope} />
        <GoldBuys {...scope} />
        <RealWage {...scope} />
        <PriceStructure {...scope} />
        <GoldRuler {...scope} />
        <ChinaUs {...scope} />
        <Claims ds={ds} />
        <Methods ds={ds} />
      </main>
      <footer className="wrap">
        数据与代码：<a href="https://github.com/GYZ001/costmodel">github.com/GYZ001/costmodel</a> ·
        数据集由 GitHub Actions 定时从官方来源重新抓取并校验；任何数字都可以在“方法与来源”中找到原始文件与校验和。
      </footer>
    </>
  );
}

function AddCountry({ ds, picks, onAdd }: { ds: Dataset; picks: string[]; onAdd: (iso: string) => void }) {
  const options = useMemo(
    () =>
      Object.entries(ds.countries)
        .filter(([iso]) => !picks.includes(iso))
        .sort((a, b) => countryName(a[1]).localeCompare(countryName(b[1]), "zh-CN")),
    [ds, picks],
  );
  return (
    <select
      value=""
      aria-label="添加经济体"
      onChange={(e) => {
        if (e.target.value) onAdd(e.target.value);
      }}
    >
      <option value="">＋ 添加经济体…</option>
      {options.map(([iso, c]) => (
        <option key={iso} value={iso}>
          {countryName(c)}
        </option>
      ))}
    </select>
  );
}
