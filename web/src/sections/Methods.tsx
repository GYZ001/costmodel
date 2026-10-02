import type { Dataset } from "../types";
import { countryName, fmt } from "../lib";

const KIND: Record<string, string> = {
  unit: "无法证明同一货币单位",
  missing: "发布方未发布",
  notes: "发布方注明不能用",
  check: "数量级 / 时间单位 / 工时核对不通过",
  area: "地区代码无法对应",
};

const SCOPE: Record<string, string> = {
  fx: "官方汇率",
  ppp: "购买力平价",
  cohd: "健康饮食成本",
  currency: "货币代码",
  hours: "工时（ILOSTAT）",
  area: "地区代码",
  "wage:cn": "工资（国家统计局）",
  "wage:bls": "工资（美国劳工统计局）",
  "wage:oecd": "工资（OECD）",
  "wage:ilo_monthly_mean": "工资（ILOSTAT 平均月薪）",
  "wage:ilo_monthly_median": "工资（ILOSTAT 中位月薪）",
  "wage:ilo_hourly_mean": "工资（ILOSTAT 平均时薪）",
  "wage:ilo_hourly_median": "工资（ILOSTAT 中位时薪）",
};

/** One row per economy, data item and kind of reason: the excluded years and the first reason given. */
function groupExclusions(ds: Dataset) {
  const groups = new Map<string, { area: string; scope: string; kind: string; years: string[]; detail: string }>();
  for (const e of ds.exclusions) {
    const k = `${e.area}|${e.scope}|${e.kind}`;
    const g = groups.get(k) ?? { area: e.area, scope: e.scope, kind: e.kind, years: [], detail: e.detail };
    g.years.push(e.year);
    groups.set(k, g);
  }
  return [...groups.values()].sort((a, b) => a.area.localeCompare(b.area) || a.scope.localeCompare(b.scope) || a.kind.localeCompare(b.kind));
}

function yearSpan(ys: string[]): string {
  const s = [...ys].sort();
  return s.length === 1 ? s[0] : `${s[0]}–${s[s.length - 1]}（${s.length} 年）`;
}

// The branch the site and its dataset were built from (set by the Pages build, .github/workflows/pages.yml).
const BRANCH: string = import.meta.env.VITE_DATA_BRANCH || "main";

export function Methods({ ds }: { ds: Dataset }) {
  const repo = `https://github.com/GYZ001/costmodel/blob/${BRANCH}/`;
  return (
    <section className="block" id="method">
      <h2>方法与来源</h2>
      <p className="sub">每个数字都能追溯到官方发布的原始文件。数据管道的代码、原始快照和校验结果都在仓库里。</p>

      <div className="grid2">
        <div className="card">
          <h3>计算公式</h3>
          <ul className="small" style={{ paddingLeft: 18, margin: "6px 0" }}>
            <li>当地金价（本币/克）= 当年国际金价年均（美元/盎司）÷ 31.1034768 × 当年平均汇率（本币/美元）</li>
            <li>① 每小时可换黄金（克）= 时薪（本币）÷ 当地金价</li>
            <li>② 1 克黄金可买健康饮食（天）= 当地金价 ÷ 一人一天最低成本健康饮食（本币）</li>
            <li>② 1 克黄金的购买力（美国物价下的美元）= 美元金价（每克）÷ 居民消费价格水平（PPP ÷ 汇率）</li>
            <li>③ 购买力平价时薪 = 时薪 ÷ 居民消费 PPP = ① × ②（管道里对每条记录都做了这个恒等式校验）</li>
            <li>OECD 数据：时薪 = 全职当量平均年薪 ÷（全职雇员通常周工时 × 52）</li>
            <li>ILOSTAT 只有月薪的经济体：时薪 = 月薪 ÷（同一调查的每周实际工时 × 52 ÷ 12）；同一调查没有工时的，只用于月薪口径</li>
            <li>中国：时薪 = 年工资 ÷ 12 ÷（企业就业人员周平均工作时间 × 52 ÷ 12），工时取本项目存档的该年各月数值的平均（不少于 6 个月，否则不折算时薪）</li>
          </ul>
        </div>
        <div className="card">
          <h3>需要注意的口径差异</h3>
          <ul className="small" style={{ paddingLeft: 18, margin: "6px 0" }}>
            <li>平均工资通常高于中位数（少数高收入者把平均拉高）。橙点是与条形同一调查发布的中位数；条形来自 OECD 或该调查没有中位数时不画，以免把不同来源的数字当成同一个分布。</li>
            <li>ILOSTAT 汇总各国官方来源（劳动力调查、企业调查、行政记录），口径因国而异。发布方对每条记录的注释（如只覆盖城镇、只含私营部门、税后、只含全职）原文显示在悬停提示和数据表里；注释表明只覆盖部分雇员的记录在标签上注明“覆盖范围有限”。
              选用顺序：OECD → ILOSTAT 覆盖全国全体雇员的记录 → 国家统计机构自己的数据（覆盖范围按其原文说明）→ ILOSTAT 覆盖范围有限的记录。</li>
            <li>ILOSTAT 注明为“实际值”（按某基期价格）、不是平均或中位工资（如最低工资）、时间单位与指标不符、或观测状态为“不可靠”的记录，不参与计算；其他注释（如“使用时须谨慎”）原文显示。</li>
            <li>数量级和时间单位：同一调查的月薪与时薪，按该调查实测工时应相差不超过 ×/÷{fmt(ds.constants.time_factor, 2)}（“周”与“月”之比 4.33 的对数中点），且月薪 ÷ 时薪在 1 到 744 小时之间；
              不同来源或不同口径之间只有相差超过 ×/÷{fmt(ds.constants.unit_gap, 2)}（一个“周”与“月”之差）才认为是单位或数量级错误，较小的差距可能只是口径不同；
              一个月的工资超过人均全年 GDP 的，视为时间单位无法确定。对不上又无法判断是哪一个时，一并不用。</li>
            <li>同一来源相邻年份的变化，与同期名义人均收入（世界银行居民消费或 GDP ÷ 人口）的变化相差超过 ×/÷{fmt(ds.constants.level_bound, 2)}（{ds.constants.level_basis}）时，
              说明中注明“口径或数量级可能有变化”，历年曲线在那里断开；口径注释不同的两年，相差超过 ×/÷{fmt(ds.constants.unit_gap, 2)} 才注明。</li>
            <li>中国没有覆盖全体雇员的单一平均工资；国家统计局发布的城镇非私营单位、城镇私营单位、规模以上企业和农民工四种口径都列出（见“中美细看”），统计范围按其原文说明。</li>
            <li>“最低成本健康饮食”只覆盖食物，并且选的是最便宜的可得食物，不代表普通家庭的实际开销；住房、医疗、教育、社保等决定生活质量的大项不在食物篮子里，请结合“什么贵什么便宜”和购买力平价看。</li>
            <li>所有经济体都用同一参考年份的工资、汇率、金价和物价；该年没有可核对工资数据的经济体不出现在图中。页面顶部列出缺数据的 G20 成员（选“全部”时列出缺数据的重点对比经济体）。</li>
            <li>按月薪比较不需要任何工时假设；按时薪比较依赖工时数据，没有同口径工时的经济体只出现在按月薪的视图里。</li>
          </ul>
        </div>
      </div>

      <div className="card">
        <h3>交叉校验（每次刷新自动运行，任何一项失败都不会发布新数据）</h3>
        <div className="table-scroll" style={{ maxHeight: "none" }}>
          <table className="data">
            <thead><tr><th className="l">校验</th><th className="l nw">结果</th><th className="l">详情</th></tr></thead>
            <tbody>
              {ds.checks.map((c) => (
                <tr key={c.id}>
                  <td className="l" style={{ minWidth: 200 }}>{c.title}</td>
                  <td className={`l nw status-${c.status}`}>{c.status === "pass" ? "✓ 通过" : c.status === "warn" ? "! 提示" : c.status === "info" ? "ⓘ 概况" : "✗ 失败"}</td>
                  <td className="l small ink2" style={{ minWidth: 360 }}>{c.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>剔除的记录（{ds.exclusions.length} 条）</h3>
        <p className="small ink2" style={{ margin: "0 0 8px" }}>
          每个数字都要把一家机构的数（工资）除以另一家机构的数（汇率、购买力平价、饮食成本），两者必须是同一种货币单位。
          货币单位改值或欧元转换的倍数最小是 1.42（拉脱维亚），所以“相差不超过 ×/÷{fmt(ds.constants.max_factor, 1)}”就能证明同一单位，但不证明是同一个数。
          汇率和购买力平价只由世界银行自己的数据证明：官方汇率与“GDP 本币值 ÷ 美元值”、购买力平价与“居民消费本币值 ÷ 国际元值”相差不超过 ×/÷{fmt(ds.constants.max_factor, 1)}；
          世界银行缺这两项时，用 ICP 2021 的居民消费价格水平（没有货币单位）× 官方汇率核对 2021 年的购买力平价；
          该年没有可核对的数据时，沿用相邻年份的核对（数值变化不超过 ×/÷{fmt(ds.constants.max_factor, 1)}，单位不可能在其间改变）。
          工资和饮食成本再与已证明的汇率或购买力平价对上：ILOSTAT 工资 ÷ 汇率（或 ÷ 购买力平价）要与 ILOSTAT 自己发布的美元（或 PPP）换算值相符；
          健康饮食成本的本币值 ÷ PPP 值要与购买力平价相符；OECD 不变价本币工资 ÷ PPP 美元值要与基期的购买力平价相符；国家统计机构标明的货币要与已证明的货币一致。
          证明不了的输入不参与计算。判断只看数值，不针对任何特定国家；每条剔除的种类、原因与数字如下。
        </p>
        <details>
          <summary>按经济体查看</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th className="l">经济体</th><th className="l">数据</th><th className="l">种类</th><th className="l">年份</th><th className="l">原因（首条）</th></tr></thead>
              <tbody>
                {groupExclusions(ds).map((g) => (
                  <tr key={`${g.area}|${g.scope}|${g.kind}`}>
                    <td className="l">{ds.countries[g.area] ? countryName(ds.countries[g.area]) : g.area}</td>
                    <td className="l small">{SCOPE[g.scope] ?? g.scope}</td>
                    <td className="l small nw">{KIND[g.kind] ?? g.kind}</td>
                    <td className="l small">{yearSpan(g.years)}</td>
                    <td className="l small ink2" style={{ minWidth: 320 }}>{g.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <div className="card">
        <h3>数据来源与原始快照</h3>
        <div className="table-scroll" style={{ maxHeight: "none" }}>
          <table className="data">
            <thead><tr><th className="l">发布机构 / 数据集</th><th className="l">用途</th><th className="l">许可</th><th>快照</th></tr></thead>
            <tbody>
              {ds.sources.map((s) => (
                <tr key={s.prefix}>
                  <td className="l">
                    <div>{s.publisher}</div>
                    <div className="small"><a href={s.landing}>{s.title}</a></div>
                  </td>
                  <td className="l small ink2">{s.use}</td>
                  <td className="l small">{s.license}</td>
                  <td className="small">
                    <details>
                      <summary>{s.snapshots.length} 个文件 · 最近抓取 {latest(s.snapshots.map((x) => x.retrieved_at))}</summary>
                      <table className="data" style={{ marginTop: 6 }}>
                        <tbody>
                          {s.snapshots.map((x) => (
                            <tr key={x.key}>
                              <td className="l"><a href={repo + x.path}>{x.path.replace("data/raw/", "")}</a>{x.status === "stale" ? " ⚠ 本次未更新" : ""}</td>
                              <td className="l"><a href={x.url}>原始地址</a></td>
                              <td className="l mono" title={x.sha256}>{x.sha256.slice(0, 12)}…</td>
                              <td>{x.retrieved_at.replace("T", " ").replace("+00:00", " UTC")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          快照 = 发布机构返回的原始字节，未做任何修改；SHA-256 可用于核对文件未被改动。
          刷新方式：数据管道代码有改动并推送时自动运行；也可在仓库 Actions 页面选择 “data-refresh”，点击 “Run workflow” 手动运行；工作流合并到默认分支后，还会每天 07:23（UTC）自动运行（GitHub 只按默认分支上的定时设置运行）。
          “数据来源与原始快照”只列本次生成数据集时读取的文件；仓库里还保留着以前用过的快照，便于审计。
          原始文件链接指向构建本页的分支 {BRANCH}。
        </p>
      </div>
    </section>
  );
}

function latest(xs: string[]): string {
  const m = xs.sort().pop();
  return m ? m.slice(0, 10) : "—";
}
