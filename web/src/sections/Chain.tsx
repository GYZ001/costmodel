import type { Scope } from "../App";
import { countryName, fmt, minutes, money, primaryWage, sig, wageCurrency, wageLabel } from "../lib";

export function ChainSection({ ds, year, view, picks }: Scope) {
  const hourly = view === "hourly";
  const unit = hourly ? "小时" : "月";
  const all = picks.map((iso) => {
    const c = ds.countries[iso];
    const row = c?.years[year];
    const w = primaryWage(row, view);
    const lcu = hourly ? w?.hourly_lcu : w?.monthly_lcu;
    return { iso, c, row, w, lcu };
  });
  const rows = all.flatMap((r) => (r.c && r.row && r.w && r.lcu ? [{ ...r, c: r.c, row: r.row, w: r.w, lcu: r.lcu, cur: wageCurrency(r.w, r.c) }] : []));
  const missing = all.filter((r) => r.c && !rows.some((x) => x.iso === r.iso)).map((r) => countryName(r.c));
  const ex = rows.find((r) => r.row.gold_lcu_g && r.row.cohd.total);
  const goldPer = (w: (typeof rows)[number]["w"]) => (hourly ? w.hourly_gold_g : w.monthly_gold_g);
  const pppPer = (w: (typeof rows)[number]["w"]) => (hourly ? w.hourly_ppp : w.monthly_ppp);

  return (
    <section className="block" id="chain">
      <h2>三步换算：劳动 → 黄金 → 商品</h2>
      <p className="sub">
        同一套计算对所有经济体一视同仁：先算一{hourly ? "小时" : "个月"}工资能换多少克黄金，再算一克黄金在当地能买多少东西，两者相乘就是这份劳动的真实购买力。
      </p>

      {ex && (
        <div className="chain" aria-label={`${countryName(ex.c)} 的计算示例`}>
          <div className="step">
            <div className="k">① 劳动 → 黄金（{countryName(ex.c)}，{year} 年）</div>
            <div className="v">{sig(goldPer(ex.w))} 克/{unit}</div>
            <div className="f">
              {hourly ? "时薪" : "月薪"} {money(ex.lcu, ex.cur)} ÷ 当地金价 {money(ex.row.gold_lcu_g, ex.cur)}/克
            </div>
          </div>
          <div className="arrow" aria-hidden>→</div>
          <div className="step">
            <div className="k">② 黄金 → 商品</div>
            <div className="v">1 克 ≈ {sig(ex.row.cohd_days_per_g)} 天健康饮食</div>
            <div className="f">
              金价 {money(ex.row.gold_lcu_g, ex.cur)}/克 ÷ 一人一天最低成本健康饮食 {money(ex.row.cohd.total, ex.cur)}
            </div>
          </div>
          <div className="arrow" aria-hidden>→</div>
          <div className="step">
            <div className="k">③ 劳动 → 商品（①×②）</div>
            <div className="v">{unit === "月" ? "1 个月" : `1 ${unit}`} ≈ {sig(ex.row.cohd.total ? ex.lcu / ex.row.cohd.total : null)} 天健康饮食</div>
            <div className="f">
              = {hourly ? "时薪" : "月薪"} ÷ 饮食成本，黄金在这里被约掉
              {hourly && <>；换句话说，挣够一天的健康饮食要工作 {minutes(ex.w.minutes_per_cohd_day)}</>}
            </div>
          </div>
        </div>
      )}

      <div className="callout">
        <strong>黄金只是换了一把尺子。</strong>
        本页各地金价按“美元金价 × 汇率”计算，所以同一时间点上，两国“能换几克金”之比，等于按市场汇率换算的美元工资之比——黄金本身并不剥离汇率。
        真正改变结论的是第②步：同样一克黄金，在物价低的地方能买到更多东西。第③步里黄金被约掉，结果与用不用黄金计价无关。
      </div>

      <div className="card">
        <h3>重点经济体对比（{year} 年，按{hourly ? "时薪" : "月薪"}）</h3>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th className="nw">经济体</th>
                <th className="l">工资口径</th>
                <th>{hourly ? "时薪" : "月薪"}（本币）</th>
                <th>当地金价（本币/克）</th>
                <th>① 克金/{unit}</th>
                <th>② 1 克金 = 几天健康饮食</th>
                <th>③ {unit === "月" ? "1 个月" : `1 ${unit}`} = 几天健康饮食</th>
                {hourly && <th>挣一天健康饮食要工作</th>}
                <th>购买力平价{hourly ? "时薪" : "月薪"}（国际元）</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ iso, c, row, w, lcu, cur }) => (
                <tr key={iso}>
                  <td className="nw">{countryName(c)}</td>
                  <td className="l small ink2" title={w.caveat || undefined}>{wageLabel(w, view)}</td>
                  <td>{money(lcu, cur)}</td>
                  <td>{fmt(row.gold_lcu_g, (row.gold_lcu_g ?? 0) > 1000 ? 0 : 1)}</td>
                  <td>{sig(goldPer(w))}</td>
                  <td>{sig(row.cohd_days_per_g)}</td>
                  <td>{row.cohd.total ? sig(lcu / row.cohd.total) : "—"}</td>
                  {hourly && <td>{minutes(w.minutes_per_cohd_day)}</td>}
                  <td>{fmt(pppPer(w), hourly ? 1 : 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          {missing.length > 0 && <>{year} 年没有同口径{hourly ? "时薪" : "月薪"}数据：{missing.join("、")}。</>}
          “健康饮食”指世界银行“Food Prices for Nutrition”数据库中一人一天的“最低成本健康饮食”：用当地最便宜的可得食物，凑够一份包含六类食物的健康饮食所需的花费。
          “—”表示该项的输入未能证明与世界银行本币序列同一货币单位，或缺少数据（原因见“方法与来源”的剔除记录）。
          国际元＝按居民消费购买力平价换算、以美国价格为基准的购买力。中国的工资口径与工时说明见“中美细看”。
        </p>
      </div>
    </section>
  );
}
