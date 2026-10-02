import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { dumbbellOption, rankingHeight, rankingOption, stackedOption, type RankItem } from "../charts";
import { countryName, fmt, foodGroupYears, minutes, primaryWage, sig, useThemeVersion, wageLabel, wageNotes } from "../lib";
import type { CohdKey } from "../types";
import { useRows } from "./GoldPerHour";

const GROUPS: { key: CohdKey; name: string }[] = [
  { key: "staples", name: "主食（谷物、薯类）" },
  { key: "vegetables", name: "蔬菜" },
  { key: "fruits", name: "水果" },
  { key: "animal", name: "动物性食物（肉蛋奶鱼）" },
  { key: "legumes", name: "豆类、坚果与种子" },
  { key: "oils", name: "油脂" },
];

export function RealWage(scope: Scope) {
  const theme = useThemeVersion();
  const rows = useRows(scope);
  const hourly = scope.view === "hourly";
  const usRow = scope.ds.countries.USA?.years[scope.year];
  const usW = primaryWage(usRow, scope.view);

  // Economies with a primary wage that cannot be drawn: no proven exchange rate or PPP that year.
  const undrawn = useMemo(
    () => rows.filter(({ row }) => {
      const w = primaryWage(row, scope.view);
      return w && !((hourly ? w.hourly_gold_g : w.monthly_gold_g) && (hourly ? w.hourly_ppp : w.monthly_ppp));
    }).map(({ c }) => countryName(c)),
    [rows, hourly, scope.view],
  );

  const dumb = useMemo(() => {
    const ug = hourly ? usW?.hourly_gold_g : usW?.monthly_gold_g;
    const up = hourly ? usW?.hourly_ppp : usW?.monthly_ppp;
    if (!ug || !up) return [];
    return rows.flatMap(({ iso, c, row }) => {
      const w = primaryWage(row, scope.view);
      const g = hourly ? w?.hourly_gold_g : w?.monthly_gold_g;
      const p = hourly ? w?.hourly_ppp : w?.monthly_ppp;
      if (!w || !g || !p) return [];
      return [{
        name: countryName(c),
        a: (g / ug) * 100,
        b: (p / up) * 100,
        highlight: scope.picks.includes(iso),
        tip: [`对比基准：美国 ${scope.year} 年 = 100（${wageLabel(usW!, scope.view)}）`, ...wageNotes(w, scope.view, c, 160)],
      }];
    });
  }, [rows, usW, hourly, scope.view, scope.picks, scope.year]);

  const dietMinutes: RankItem[] = useMemo(
    () =>
      rows.flatMap(({ iso, c, row }) => {
        const w = primaryWage(row, "hourly");
        if (!w?.minutes_per_cohd_day) return [];
        return [{
          id: iso,
          name: countryName(c),
          value: w.minutes_per_cohd_day,
          highlight: scope.picks.includes(iso),
          tip: [...wageNotes(w, "hourly", c, 160), `一人一天最低成本健康饮食 ${fmt(row.cohd.total, 2)}（本币）`],
        }];
      }),
    [rows, scope.picks],
  );

  // The food-group split exists only for some benchmark years (in the archive so far: 2021); the chart uses the latest.
  const groupYears = useMemo(() => foodGroupYears(scope.ds), [scope.ds]);
  const GROUP_YEAR = groupYears[groupYears.length - 1] ?? "";
  const diet = useMemo(() => {
    return Object.entries(scope.ds.countries)
      .filter(([iso, c]) => scope.group === "all" || c.g20 || scope.picks.includes(iso))
      .flatMap(([iso, c]) => {
        const row = c.years[GROUP_YEAR];
        const w = primaryWage(row, "hourly");
        if (!row || !w?.hourly_lcu || !row.cohd.total || GROUPS.some((g) => row.cohd[g.key] == null)) return [];
        const parts = GROUPS.map((g) => ((row.cohd[g.key] as number) / w.hourly_lcu!) * 60);
        return [{
          name: countryName(c),
          parts,
          total: parts.reduce((a, b) => a + b, 0),
          highlight: scope.picks.includes(iso),
          tip: wageNotes(w, "hourly", c, 160),
        }];
      });
  }, [scope.ds, scope.group, scope.picks, GROUP_YEAR]);

  const monthDays: RankItem[] = useMemo(
    () =>
      rows.flatMap(({ iso, c, row }) => {
        const w = primaryWage(row, "monthly");
        if (!w?.cohd_days_per_month) return [];
        return [{
          id: iso,
          name: countryName(c),
          value: w.cohd_days_per_month,
          highlight: scope.picks.includes(iso),
          tip: [...wageNotes(w, "monthly", c, 160), `一人一天最低成本健康饮食 ${fmt(row.cohd.total, 2)}（本币）`],
        }];
      }),
    [rows, scope.picks],
  );

  const dOpt = useMemo(() => dumbbellOption({ rows: dumb, aName: "按黄金克数（=市场汇率）", bName: "按购买力（PPP）" }), [dumb, theme]);
  const sOpt = useMemo(() => stackedOption({ rows: diet, partNames: GROUPS.map((g) => g.name), format: (v) => `${fmt(v, v > 0 && v < 10 ? 1 : 0)} 分` }), [diet, theme]);
  const dmOpt = useMemo(() => rankingOption({ items: dietMinutes, valueName: "挣够一天健康饮食需工作", format: (v) => `${sig(v, 2)} 分钟` }), [dietMinutes, theme]);
  const mOpt = useMemo(() => rankingOption({ items: monthDays, valueName: "一个月工资可买健康饮食", format: (v) => `${sig(v, 3)} 天` }), [monthDays, theme]);

  return (
    <section className="block" id="real">
      <h2>③ 劳动 → 商品：真实购买力差多少（{scope.year} 年）</h2>
      <p className="sub">
        灰点是“{hourly ? "每小时" : "每月"}能换的黄金克数”相对美国的水平，蓝点是扣除当地物价后的真实购买力（按购买力平价）相对美国的水平。
        两点之间的距离，就是当地物价把差距“压缩”（或放大）的部分。
      </p>
      <div className="card">
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--deemph)", borderRadius: "50%" }} />按黄金克数（等于按市场汇率）</span>
          <span><span className="sw" style={{ background: "var(--accent)", borderRadius: "50%" }} />按购买力平价（扣除当地居民消费物价）</span>
        </div>
        {dumb.length ? (
          <Chart option={dOpt} height={rankingHeight(dumb.length)} ariaLabel="工资相对美国：按黄金克数与按购买力" />
        ) : (
          <p className="muted">该年美国缺少同口径数据，无法以美国为基准。</p>
        )}
        <p className="note">
          对数刻度，美国 = 100。按黄金克数的比值与按市场汇率的美元工资比值相同，因为各地金价都等于美元金价乘以汇率。
          {undrawn.length > 0 && <> 有{hourly ? "时薪" : "月薪"}但该年缺少可核对的汇率或购买力平价、因而没有画出：{undrawn.join("、")}（原因见“方法与来源”的剔除记录）。</>}
        </p>
        <details>
          <summary>查看数据表</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>经济体</th><th>按黄金克数（美国=100）</th><th>按购买力（美国=100）</th><th>物价带来的倍数变化</th></tr></thead>
              <tbody>
                {[...dumb].sort((x, y) => y.b - x.b).map((r) => (
                  <tr key={r.name}><td>{r.name}</td><td>{fmt(r.a, 1)}</td><td>{fmt(r.b, 1)}</td><td>{fmt(r.b / r.a, 2)}×</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      {hourly ? (
        <>
          <div className="card">
            <h3>挣够一个人一天的健康饮食，要工作多少分钟？（{scope.year} 年）</h3>
            <p className="small ink2" style={{ margin: "0 0 8px" }}>
              一人一天最低成本健康饮食 ÷ 主要口径的时薪 × 60。分钟数越少，同样的工作时间能吃得越好。
            </p>
            <div className="legend">
              <span><span className="sw" style={{ background: "var(--accent)" }} />重点对比的经济体</span>
              <span><span className="sw" style={{ background: "var(--deemph)" }} />其他经济体</span>
            </div>
            <Chart option={dmOpt} height={rankingHeight(dietMinutes.length)} ariaLabel="挣够一天健康饮食需要的工作分钟数" />
          </div>
          <div className="card">
            <h3>这些分钟花在哪类食物上（{GROUP_YEAR} 年基准）</h3>
            <p className="small ink2" style={{ margin: "0 0 8px" }}>
              本项目存档的世界银行数据只有 {groupYears.join("、") || "—"} 年有六类食物的分项成本，所以这张图用 {GROUP_YEAR || "—"} 年：分项成本与该年时薪配对。
            </p>
            <div className="legend">
              {GROUPS.map((g, i) => (
                <span key={g.key}><span className="sw" style={{ background: `var(--s${i + 1})` }} />{g.name}</span>
              ))}
            </div>
            {diet.length ? (
              <Chart option={sOpt} height={rankingHeight(diet.length)} ariaLabel="2021 年一天健康饮食需要的工作分钟数，按食物类别拆分" />
            ) : (
              <p className="muted">所选范围内没有 2021 年的分项数据。</p>
            )}
            <details>
              <summary>查看数据表</summary>
              <div className="table-scroll">
                <table className="data">
                  <thead><tr><th>经济体</th><th>合计</th>{GROUPS.map((g) => <th key={g.key}>{g.name}（分钟）</th>)}</tr></thead>
                  <tbody>
                    {[...diet].sort((a, b) => a.total - b.total).map((r) => (
                      <tr key={r.name}><td>{r.name}</td><td>{minutes(r.total)}</td>{r.parts.map((p, i) => <td key={i}>{fmt(p, 1)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        </>
      ) : (
        <div className="card">
          <h3>一个月的平均工资，够一个人吃多少天健康饮食？</h3>
          <div className="legend">
            <span><span className="sw" style={{ background: "var(--accent)" }} />重点对比的经济体</span>
            <span><span className="sw" style={{ background: "var(--deemph)" }} />其他经济体</span>
          </div>
          <Chart option={mOpt} height={rankingHeight(monthDays.length)} ariaLabel="一个月工资可买的健康饮食天数" />
          <p className="note">月薪 ÷ 一人一天最低成本健康饮食。天数越多，同样一个月的工作能吃得越好。</p>
        </div>
      )}
    </section>
  );
}
