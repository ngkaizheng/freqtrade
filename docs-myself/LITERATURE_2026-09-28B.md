# 文献更新 2 — 方向切换与多空不对称（2026-09-28 第二轮检索）

**承接：** `LITERATURE_2026-09-28.md`（第一轮：Kim & Hansen、Pindza、He et al.、Grobys 2025）
**检索范围：** arXiv API、Crossref、OpenAlex、直连 PDF。
**⚠ 检索受限，已声明：** Bing 本轮返回 0 次结果并降级；SSRN 对所有客户端返回 403；
MDPI 返回 403；Semantic Scholar 限流 429。**没有拿到 Google Scholar / EconLit / RePEc 和出版商付费墙。**
**所以下面每一个「没找到」都只意味着「在 arXiv + Crossref + OpenAlex + 可达网页范围内没找到」，
不等于可证明地不存在。**

---

## 0. 最重要的两条

**1. Nefedov (2026), SSRN 7350238，2026-09-28 当天上传（预印本）——
这是本项目至今最贴场所的外部锚点。**

> **「Auditing six standard factors—momentum, short-term reversal, volatility,
> size/liquidity, funding-carry, and beta—on 137 Binance USDT-perpetual contracts
> over 2020-2024, we compare a naïve protocol … against a rigorous one …**
> **Naïve evaluation inflates the annualized Sharpe ratio by 3.6× on average,
> and under the baseline protocol none of the six factors survives deflation;
> four collapse to a negative out-of-sample Sharpe. A decomposition attributes
> most of the gap to trading frictions rather than to in-sample over-optimization.
> Funding-carry, the strongest naïve performer, survives only under optimistic
> cost assumptions」**

**137 个 Binance USDT 永续、2020–2024，与本项目的 104 币面板、2023–2026 几乎同场所同品种。**
而它的两条结论**独立地印证了本项目这两天的两个核心发现：**
- **momentum 扣多重检验后不存活**（对应本项目的 E#3/E#6、Grobys 2025、本次 4h 线的 t=−0.15）；
- **「差距主要来自交易摩擦，而不是样本内过度优化」**——
  这正是本项目「成本是约束」这一整条主线的外部版本。

⚠ 局限：**只拿到摘要**，SSRN 403，取自 Istina 镜像，**最后一句在单词中途被截断**；
作者自述是加密衍生品从业者，**按从业者研究对待，不按学术对待**。

**2. 「加密多空腿不对称」在文献里是一个空白，不是一个已确认或已否证的规律。**

**四篇全文读过的论文里，没有任何一篇分别报告多头腿和空头腿的表现。**
唯一讨论多空不对称的 Nguyen (2026) **指向相反方向**。
**所以本项目的 12 个格子多头腿全负，正确写法是「文献没有拆分这条腿」，
不是「文献确认多头腿无效」，也不是「本项目复制失败」。**

---

## 1. 与本项目方向切换直接相关的四篇

| 来源 | 构造 / 场所 / 期间 | 成本 | 数字 | 与我的结果的关系 |
|---|---|---|---|---|
| **Romo, Soto, Vega, Crawford, Salinas & Becerra-Rozas (2025)**, *Mathematics* 13(16):2629, **同行评议**, doi:10.3390/math13162629 | **和我的构造完全一样**：快 SMA 上穿慢 SMA 做多、下穿做空，4 状态 FSM。**Binance BTCUSDT 期货，15 分钟，2020-01→2022-09，单一资产** | ⚠ **Eq. 11 符号化扣费，全文从未给出费率**——**净成本声明不可验证** | 34 组训练/测试切分，平均测试 ROI **1.079**（≈每 2 个月 +7.9%）；基准 Buy&Hold 1.012、固定 2-SMA 1.026、随机游走 0.995。Wilcoxon p = 0.018/0.031/0.024 | 唯一一篇同行评议的「MA 交叉在 Binance 期货上净改善」声明，**但费率未披露，且 8 个重叠窗口下 p=0.018 基本是 n=8 的下限**——「和 8 个观测能显示的显著程度一样」，不是显著 |
| **Nguyen (2026)**, arXiv:2602.11708, **预印本** | Binance 期货 150+ 永续，6 小时，2021-01→2024-12，IS 2021 / OOS 2022-2024 | **有，且披露**：taker 4 bps/笔、与 5 分钟成交量成比例的滑点、8 小时资金费。成本敏感度 0/4/8/12 bps → Sharpe 2.87/2.41/2.01/1.62 | AdaptiveTrend 70/30：年化 **40.5%**，**Sharpe 2.41**，MDD −12.7% | **⚠ 指向相反。** 作者称加密是「结构性偏多」的资产，**空头腿才是难的那一侧**（γ_L=1.3 vs γ_S=1.7），70/30 优于 50/50（2.41 vs 2.12）。**但从未报告纯多头臂**，无法回答多头腿是否净正；OOS 窗口在摘要/§4.1/图 1 三处写法不一致；**约一半的 Sharpe 来自样本内选择**（固定参数消融只有 1.34） |
| **Kumar & Jenefer (2026)**, JOIREM 4(4) — ⚠ **弱场所、3 页、作者用 gmail 地址、两处引用是错的** | 波动率目标 MOP 式 TSMOM，252 日回看，月度调仓，40% 波动目标上限 2x，BTC-USD/ETH-USD/IBIT/FBTC/GLD/SPY 日线 2018-01→2026-03 | **毛（gross）**——论文自己把「纳入交易成本」列为未来工作 | 组合前 Sharpe 0.823 / 后 1.223，**t 检验 p=0.5835（不显著）**。「TSMOM **在盘前牛市跑输 Buy&Hold 7.67%**（10.65% vs 18.32%），盘后跑赢 **20.95%**」 | **形状与我的不对称一致**（价值集中在空头区间），**但作者归因于波动率目标而非多头腿弱**，且**是毛数字** |
| **Rozario, Holt, West & Ng (2020)**, arXiv:2009.12155, 预印本 | 与我同样的构造（快 MA 上穿买、下穿卖），BTCUSD **现货**，Bitstamp，小时级，2011-09→2019-12 | **毛**：「We assumed **negligible transaction fees, bid-offer spread, slippage and market impact**」 | 样本内最优 Sharpe 1.09（SMA）/1.35（EMA）。Walkforward BTCUSD：73,700% 累计、**255% 年化** | **⚠ 那 255% 是 2011–2016（BTC 襁褓期，作者自己前向填充了 72,299 行中的 5,835 行）。作者自己的近期切片结论：「**sub-par** and **negative Sharpe ratios**」、「**no predictable and attractive Sharpe ratios**」、「**the notable absence of profitable intra-day trend following strategies for BTCUSD spot markets**」 |

**Gbadebo (2026)**, *Buhalterinės apskaitos teorija ir praktika*, doi:10.15388/batp.2026.1 — EMA 交叉 TSMOM，8 个主流币 2020-01→2025-10，**年化 31.96%**。**⚠ 摘要未披露成本，全文取不到，净/毛 UNVERIFIED。** 同样没有多空拆分。

---

## 2. 又一个同行评议的加密动量空结果（与已有的 2025 FMP 那篇不同作者组的新作）

> **Grobys, Sandretto & Äijö (2026), "On survivor cryptocurrency momentum",
> *Finance Research Letters*, doi:10.1016/j.frl.2026.109602. 同行评议。**
> 9 个持续为前 100 的「survivor」币，2017-01→2024-08，周频。
> **「The survivor cryptocurrency momentum portfolio (SCMP) does not generate
> significant payoffs… Significant payoffs documented for momentum strategies
> are an artefact of coins that are only temporarily accessible for trading.」**
> 且「even after trimming, the profitability of plain cryptocurrency momentum is
> **highly sample-dependent**」。
> **成本假设未在取到的 highlights 中披露 — UNVERIFIED。**
> **与 2025 FMP 那篇同一作者组，所以是加强而非重复。**

---

## 3. MOP 2012 TSMOM 在加密上的文献（按你问的三个点回答）

1. **有没有人把加密多空腿拆开？——没有。** 一篇都没有。
2. **MOP 2012「延续性在跌得最狠的指数上最强」，在加密里有没有被检验？**
   **本次检索没有找到任何检验。** 这仍是一个未验证的直觉。
3. 相关同行评议论文（**全部只确认了元数据，摘要/全文取不到**）：
   - **Borgards, O. (2021)**, *North American Journal of Economics and Finance*,
     doi:10.1016/j.najef.2021.101428 — **加密 TSMOM 的经典同行评议论文。**
     ⚠ **一个 2026 年论文把它引成「Journal of Risk and Financial Management
     14(10), 474」——那是错的**，该 DOI 指向一篇银行失败预测论文。
     **引 Borgards 请用 NAJEF 的 DOI。**
   - Proelss, Schweizer & Buchwalter, *Finance Research Letters*, doi:10.1016/j.frl.2024.106531
   - **Hsieh, Huang & Liu (2025)**, *FRL*, doi:10.1016/j.frl.2025.108356 —
     **标题正是「加密市场的状态转移与动量效应」**，最对题但摘要取不到
   - Yang, A. (2025), *FRL*, doi:10.1016/j.frl.2025.107879
   - **Zhang, C. (2026), "Cross-Sectional Dispersion and the State Dependence of
     Cryptocurrency Momentum", SSRN 6648058 — 预印本。**
     **状态依赖性最对题的未核实线索，建议优先取。**

---

## 4. 明确写下来的空白（省下后来者重复检索）

- **没有任何已发表论文单独报告加密趋势/突破信号的多头腿与空头腿表现。**
  **这是本项目目前最重要的文献空白。**
- **没有任何已发表的「失败复现 / 批评」专门针对加密上的慢 MA regime 过滤器。**
  没有人在扣成本后检验过我构造的那个东西。
- 除了 Nefedov，**2026-09-27/28 两天没有其他新论文。**

---

## 5. 一条引用可靠性警告

引用 Kumar & Jenefer (2026) 或它的参考文献之前注意：
**那是一篇 3 页的 JOIREM 论文，作者用 gmail 地址，五条实质引用里有两条是错的**
（Borgards 的期刊名错、Proelss 的期刊名错），
且**「Han, Y., et al. (2024), Time-series and cross-sectional momentum in the
cryptocurrency market, Journal of Financial Markets」在 Crossref 里根本不存在**。
**它引用的 Huang et al. 的 Sharpe 2.17 归属 UNVERIFIED，文献综述不可靠。**
上表里我只用它自己那份我直接读到的盘前/盘后数字。

---

## 6. 本次检索对本项目的净结论

1. **Nefedov (2026) 是目前最贴场所的外部锚点，独立支持本项目的两个主结论**
   （momentum 扣分后不存活；差距主要来自交易摩擦）。
2. **多空腿不对称是证据空白**——正确写法是「文献没有拆分这条腿」，
   **不是「文献支持/反对」**。
3. **最接近的两个结果形状上与我一致**（Kumar & Jenefer 牛市跑输 B&H 7.67%；
   Romo 对 B&H 只有 +6.7pp 边际），**一个指向相反**（Nguyen 把加密当结构性偏多）。
4. **Romo et al. (2025) 是唯一同行评议的「MA 交叉在 Binance 期货上净改善」声明，
   但费率从未披露、8 个重叠窗口、p 值触及 n=8 的下限——不要当作成本稳健的证据再引一次。**
