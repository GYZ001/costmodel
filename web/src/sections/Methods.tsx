import type { Dataset } from "../types";

export function Methods({ ds }: { ds: Dataset }) {
  const repo = "https://github.com/GYZ001/costmodel/blob/main/";
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
            <li>只有月薪的经济体：时薪 = 月薪 ÷（每周实际工时 × 52 ÷ 12）</li>
            <li>中国：时薪 = 年工资 ÷ 12 ÷（企业就业人员周平均工作时间 × 52 ÷ 12），该年已公布月份的工时取平均</li>
          </ul>
        </div>
        <div className="card">
          <h3>需要注意的口径差异</h3>
          <ul className="small" style={{ paddingLeft: 18, margin: "6px 0" }}>
            <li>平均工资被高收入者拉高；有中位数的经济体同时画出中位时薪（橙点）。</li>
            <li>ILOSTAT 汇总各国官方来源（劳动力调查、企业调查、行政记录），税前/税后、是否含奖金等口径因国而异，来源标注在每条记录的提示里。</li>
            <li>中国只有城镇单位和农民工的工资统计，没有全体雇员的单一平均数；三种口径都列出。</li>
            <li>“最低成本健康饮食”只覆盖食物，并且选的是最便宜的可得食物，不代表普通家庭的实际开销；住房、医疗、教育、社保等决定生活质量的大项不在食物篮子里，请结合“什么贵什么便宜”和购买力平价看。</li>
            <li>“各国最新可得年份”模式下，不同经济体的年份可能不同（已标注）；每个经济体内部的工资、汇率、金价和物价始终是同一年。</li>
          </ul>
        </div>
      </div>

      <div className="card">
        <h3>交叉校验（每次刷新自动运行，任何一项失败都不会发布新数据）</h3>
        <table className="data">
          <thead><tr><th className="l">校验</th><th className="l">结果</th><th className="l">详情</th></tr></thead>
          <tbody>
            {ds.checks.map((c) => (
              <tr key={c.id}>
                <td className="l">{c.title}</td>
                <td className={`l status-${c.status}`}>{c.status === "pass" ? "✓ 通过" : c.status === "warn" ? "! 提示" : "✗ 失败"}</td>
                <td className="l small ink2">{c.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
          刷新方式：仓库 Actions 页面的 “data-refresh” 工作流每天自动运行，也可点击 “Run workflow” 手动运行。
        </p>
      </div>
    </section>
  );
}

function latest(xs: string[]): string {
  const m = xs.sort().pop();
  return m ? m.slice(0, 10) : "—";
}
