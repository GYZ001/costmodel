import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { dumbbellOption, rankingHeight, stackedOption } from "../charts";
import { countryName, fmt, minutes, primaryWage, rowFor, useThemeVersion } from "../lib";
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
  const us = scope.ds.countries.USA;

  const dumb = useMemo(() => {
    return rows.flatMap(({ iso, c, year, row }) => {
      const w = primaryWage(row);
      const usr = us && rowFor(us, year);
      const uw = usr && primaryWage(usr.row);
      if (!w?.hourly_gold_g || !w.hourly_ppp || !uw?.hourly_gold_g || !uw.hourly_ppp) return [];
      return [{
        name: `${countryName(c)}${scope.yearMode === "latest" ? `（${year}）` : ""}`,
        a: (w.hourly_gold_g / uw.hourly_gold_g) * 100,
        b: (w.hourly_ppp / uw.hourly_ppp) * 100,
        highlight: scope.picks.includes(iso),
        tip: [`对比基准：美国 ${year} 年 = 100`, `${w.label}`],
      }];
    });
  }, [rows, us, scope.picks, scope.yearMode]);

  const diet = useMemo(() => {
    return rows.flatMap(({ iso, c, year, row }) => {
      const w = primaryWage(row);
      if (!w?.hourly_lcu || !row.cohd.total) return [];
      const parts = GROUPS.map((g) => ((row.cohd[g.key] ?? 0) / w.hourly_lcu!) * 60);
      return [{
        name: `${countryName(c)}${scope.yearMode === "latest" ? `（${year}）` : ""}`,
        parts,
        total: (row.cohd.total / w.hourly_lcu) * 60,
        highlight: scope.picks.includes(iso),
        tip: [`${w.label}`],
      }];
    });
  }, [rows, scope.picks, scope.yearMode]);

  const dOpt = useMemo(() => dumbbellOption({ rows: dumb, aName: "按黄金克数（=市场汇率）", bName: "按购买力（PPP）" }), [dumb, theme]);
  const sOpt = useMemo(() => stackedOption({ rows: diet, partNames: GROUPS.map((g) => g.name), format: (v) => `${fmt(v, v < 10 ? 1 : 0)} 分` }), [diet, theme]);

  return (
    <section className="block" id="real">
      <h2>③ 劳动 → 商品：真实购买力差多少</h2>
      <p className="sub">
        灰点是“每小时能换的黄金克数”相对美国的水平，蓝点是扣除当地物价后的真实购买力（购买力平价时薪）相对美国的水平。
        两点之间的距离，就是当地物价把差距“压缩”（或放大）的部分。
      </p>
      <div className="card">
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--deemph)", borderRadius: "50%" }} />按黄金克数（等于按市场汇率）</span>
          <span><span className="sw" style={{ background: "var(--accent)", borderRadius: "50%" }} />按购买力平价（扣除当地居民消费物价）</span>
        </div>
        <Chart option={dOpt} height={rankingHeight(dumb.length)} ariaLabel="时薪相对美国：按黄金克数与按购买力" />
        <p className="note">对数刻度，美国 = 100。按黄金克数的比值与按市场汇率的美元时薪比值相同，因为各地金价都等于美元金价乘以汇率。</p>
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

      <div className="card">
        <h3>挣够一个人一天的健康饮食，要工作多少分钟？</h3>
        <p className="small ink2" style={{ margin: "0 0 8px" }}>
          用主要工资口径的时薪，去买世界银行测算的一人一天最低成本健康饮食，并按六类食物拆开。分钟数越少，同样工作时间能吃得越好。
        </p>
        <div className="legend">
          {GROUPS.map((g, i) => (
            <span key={g.key}><span className="sw" style={{ background: `var(--s${i + 1})` }} />{g.name}</span>
          ))}
        </div>
        <Chart option={sOpt} height={rankingHeight(diet.length)} ariaLabel="一天健康饮食需要的工作分钟数，按食物类别拆分" />
        <details>
          <summary>查看数据表</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>经济体</th><th>合计</th>{GROUPS.map((g) => <th key={g.key}>{g.name}</th>)}</tr></thead>
              <tbody>
                {[...diet].sort((a, b) => a.total - b.total).map((r) => (
                  <tr key={r.name}><td>{r.name}</td><td>{minutes(r.total)}</td>{r.parts.map((p, i) => <td key={i}>{fmt(p, 1)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </section>
  );
}
