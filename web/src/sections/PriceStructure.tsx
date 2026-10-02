import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { heatmapOption } from "../charts";
import { countryName, fmt, useThemeVersion } from "../lib";

const CATS: { key: string; name: string }[] = [
  { key: "hfce", name: "居民消费合计" },
  { key: "food_nonalc", name: "食品与非酒精饮料" },
  { key: "bread_cereals", name: "面包谷物" },
  { key: "meat", name: "肉类" },
  { key: "milk_cheese_eggs", name: "奶蛋" },
  { key: "fruit", name: "水果" },
  { key: "vegetables", name: "蔬菜" },
  { key: "clothing", name: "衣着" },
  { key: "housing", name: "住房水电燃气" },
  { key: "health", name: "医疗" },
  { key: "transport", name: "交通" },
  { key: "communication", name: "通信" },
  { key: "education", name: "教育" },
  { key: "restaurants_hotels", name: "餐饮住宿" },
];

export function PriceStructure(scope: Scope) {
  const theme = useThemeVersion();
  const { ds, group, picks } = scope;
  const { rows, values, isos } = useMemo(() => {
    const isos = Object.keys(ds.icp2021_pli_us)
      .filter((iso) => ds.countries[iso] && (group === "all" ? true : ds.countries[iso].g20 || picks.includes(iso)))
      .sort((a, b) => (ds.icp2021_pli_us[b].hfce ?? 0) - (ds.icp2021_pli_us[a].hfce ?? 0));
    const rows = isos.map((iso) => countryName(ds.countries[iso]));
    const values: [number, number, number | null][] = [];
    isos.forEach((iso, r) => CATS.forEach((cat, c) => values.push([c, r, ds.icp2021_pli_us[iso][cat.key] ?? null])));
    return { rows, values, isos };
  }, [ds, group, picks]);
  const hl = useMemo(() => new Set(picks.filter((p) => ds.countries[p]).map((p) => countryName(ds.countries[p]))), [ds, picks]);
  const option = useMemo(() => heatmapOption({ rows, cols: CATS.map((c) => c.name), values, highlightRows: hl }), [rows, values, hl, theme]);
  const cn = ds.icp2021_pli_us.CHN;

  return (
    <section className="block" id="structure">
      <h2>什么贵、什么便宜：各类商品和服务的价格水平</h2>
      <p className="sub">
        世界银行国际比较项目（ICP）2021 年基准：用统一规格的商品和服务逐项比价，按市场汇率换算后与美国比较（美国 = 1）。
        红色表示比美国贵，蓝色表示比美国便宜。超市里的食品属于可贸易商品，各国价差远小于住房、医疗、餐饮等服务。
      </p>
      {cn && (
        <div className="callout">
          以中国为例（2021 年）：居民消费整体价格水平约为美国的 <strong>{fmt(cn.hfce, 2)}</strong> 倍，
          但“食品与非酒精饮料”为美国的 <strong>{fmt(cn.food_nonalc, 2)}</strong> 倍
          （肉类 {fmt(cn.meat, 2)}、奶蛋 {fmt(cn.milk_cheese_eggs, 2)}、水果 {fmt(cn.fruit, 2)}）；而住房 {fmt(cn.housing, 2)}、医疗 {fmt(cn.health, 2)}、餐饮住宿 {fmt(cn.restaurants_hotels, 2)}。
          也就是说，按市场汇率，中国超市食品并不比美国便宜，便宜的主要是服务。
        </div>
      )}
      <div className="card">
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--div-neg)" }} />比美国便宜</span>
          <span><span className="sw" style={{ background: "var(--div-mid)", border: "1px solid var(--axis)" }} />与美国相当</span>
          <span><span className="sw" style={{ background: "var(--div-pos)" }} />比美国贵</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <div style={{ minWidth: 980 }}>
            <Chart option={option} height={Math.max(220, isos.length * 26 + 60)} ariaLabel="各经济体分类价格水平热力图（美国=1）" />
          </div>
        </div>
        <p className="note">
          ICP 按统一产品规格逐项比价，是比较各国“同样东西卖多少钱”的官方依据；这里展示的是 2021 年基准年的价格结构。
          2021 年之后各国物价和汇率都有变化，不宜把这张表直接当作今天的精确价差（今天的整体物价水平见上一节“相当于在美国花多少美元”，那是世界银行按年外推的官方数）。
        </p>
      </div>
    </section>
  );
}
