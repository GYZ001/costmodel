import type { Scope } from "../App";
import { countryName, fmt, minutes, money, primaryWage, rowFor, sig } from "../lib";

export function ChainSection({ ds, yearMode, picks }: Scope) {
  const rows = picks
    .map((iso) => {
      const c = ds.countries[iso];
      const r = c && rowFor(c, yearMode);
      const w = r && primaryWage(r.row);
      return c && r && w && w.hourly_lcu ? { iso, c, year: r.year, row: r.row, w } : null;
    })
    .filter((x): x is NonNullable<typeof x> => x !== null);
  const ex = rows[0];

  return (
    <section className="block" id="chain">
      <h2>三步换算：劳动 → 黄金 → 商品</h2>
      <p className="sub">
        同一套计算对所有经济体一视同仁：先算一小时工资能换多少克黄金，再算一克黄金在当地能买多少东西，两者相乘就是一小时劳动的真实购买力。
      </p>

      {ex && (
        <div className="chain" aria-label={`${countryName(ex.c)} 的计算示例`}>
          <div className="step">
            <div className="k">① 劳动 → 黄金（{countryName(ex.c)}，{ex.year} 年）</div>
            <div className="v">{sig(ex.w.hourly_gold_g)} 克/小时</div>
            <div className="f">
              时薪 {money(ex.w.hourly_lcu, ex.c.currency)} ÷ 当地金价 {money(ex.row.gold_lcu_g, ex.c.currency)}/克
            </div>
          </div>
          <div className="arrow" aria-hidden>→</div>
          <div className="step">
            <div className="k">② 黄金 → 商品</div>
            <div className="v">1 克 ≈ {sig(ex.row.cohd_days_per_g)} 天健康饮食</div>
            <div className="f">
              金价 {money(ex.row.gold_lcu_g, ex.c.currency)}/克 ÷ 一人一天最低成本健康饮食 {money(ex.row.cohd.total, ex.c.currency)}
            </div>
          </div>
          <div className="arrow" aria-hidden>→</div>
          <div className="step">
            <div className="k">③ 劳动 → 商品（①×②）</div>
            <div className="v">1 小时 ≈ {sig(ex.w.hourly_lcu! / (ex.row.cohd.total ?? NaN))} 天健康饮食</div>
            <div className="f">
              = 时薪 ÷ 饮食成本，黄金在这里被约掉；换句话说，挣够一天的健康饮食要工作 {minutes(ex.w.minutes_per_cohd_day)}
            </div>
          </div>
        </div>
      )}

      <div className="callout">
        <strong>黄金只是换了一把尺子。</strong>
        国际金价靠跨境套利拉平，各地金价 ≈ 美元金价 × 汇率，所以同一时间点上，两国“每小时能换几克金”之比，等于按市场汇率换算的美元时薪之比——黄金本身并不剥离汇率。
        真正改变结论的是第②步：同样一克黄金，在物价低的地方能买到更多东西。第③步里黄金被约掉，结果与用不用黄金计价无关。
      </div>

      <div className="card">
        <h3>重点经济体对比</h3>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>经济体</th>
                <th>年份</th>
                <th className="l">工资口径</th>
                <th>时薪（本币）</th>
                <th>当地金价（本币/克）</th>
                <th>① 克金/小时</th>
                <th>② 1 克金 = 几天健康饮食</th>
                <th>③ 1 小时 = 几天健康饮食</th>
                <th>挣一天健康饮食要工作</th>
                <th>购买力平价时薪（国际元）</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ iso, c, year, row, w }) => (
                <tr key={iso}>
                  <td>{countryName(c)}</td>
                  <td>{year}</td>
                  <td className="l small ink2">{w.label}</td>
                  <td>{money(w.hourly_lcu, c.currency)}</td>
                  <td>{fmt(row.gold_lcu_g, row.gold_lcu_g > 1000 ? 0 : 1)}</td>
                  <td>{sig(w.hourly_gold_g)}</td>
                  <td>{sig(row.cohd_days_per_g)}</td>
                  <td>{row.cohd.total ? sig(w.hourly_lcu! / row.cohd.total) : "—"}</td>
                  <td>{minutes(w.minutes_per_cohd_day)}</td>
                  <td>{fmt(w.hourly_ppp, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          “健康饮食”指世界银行与联合国粮农组织测算的一人一天“最低成本健康饮食”（按各国膳食指南、用当地最便宜的可得食物组合），是目前覆盖国家最多、口径统一的官方食物篮子。
          国际元＝按居民消费购买力平价换算、以美国价格为基准的购买力。中国的工资口径与工时说明见“中美细看”。
        </p>
      </div>
    </section>
  );
}
