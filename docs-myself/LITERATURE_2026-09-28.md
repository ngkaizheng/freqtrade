# 文献检索 — 2026-09-28（带成本、适用于永续合约的信号）

**方法：** arXiv API、Crossref/RePEc/IDEAS、exa、通用网页。
**原则：** 只报**已核实**的来源；无法核实的明确标注。
**排除：** 用户已有的五篇（Hurst/Ooi/Pedersen 2017、Fieberg 2025、Arefev、Ammann et al.、本仓库自己的因子扫描）——除非它们与新证据**互相印证**，那正是最有价值的用法。

---

## 0. 结论

**1. 存在一个真实且重要的文献空白：没有任何同行评议的、
「日内/日频 × 加密永续 × 扣除成本后效应量够大」的信号。**
这不是搜索失败，是**发现**。

> arXiv 上 `abs:"cryptocurrency" AND abs:"transaction costs" AND cat:q-fin.TR`
> **全站只有 4 篇。** 绝大多数加密交易论文是**零成本**的。

**2. 最接近本项目信号的那篇，效应量恰好能定价本条线的死刑。**

**3. 本仓库自己的测量与它一致。** 两个独立仪器，同一家族，
一个说 5–6 bps，一个说 2.47 bps，都比成本小一个数量级。

---

## 1. 成交量/订单流尖峰 → 未来几根 bar（**决定性的一篇**）

> **Kim, Chan (Korea Information Society Development Institute);
> Hansen, Peter Reinhard (UNC Chapel Hill, Dept. of Economics).**
> **"The Quarter-Hour Effect: Periodic Algorithmic Trading and Return
> Predictability in Cryptocurrency Futures."**
> **arXiv:2607.09426**, v1 2026-07-10, v2 2026-07-16.
> **⚠ 预印本，未同行评议。** https://arxiv.org/abs/2607.09426
> ⚠ 资金披露：Hansen 承认 **Ripple University Blockchain Research Initiative (UBRI)** 资助。
> 引用前应知悉。

**场所/品种/期间：** **Binance USDT 保证金永续**，BTC/ETH/XRP/SOL/DOGE/ADA，
**2021-01-01 → 2024-10-31**，毫秒级聚合成交（含 isBuyerMaker），
每品种约 131,700 个刻钟开盘。

**「尖峰」确实存在**（原文）：
> 刻钟开盘前 10 秒相比普通刻钟的同一区间，
> 成交笔数 **+26%**、成交金额 **+32%**、绝对收益 **+26%**，**全部在 1% 水平显著**。

**预测结果在恰好是 4h 的期限上**：
> 订单失衡预测 4h / 8h / 12h 累计收益，
> **「4 到 12 小时之间，六个合约中有四个在每个期限上都达到 95% 置信水平」**
> （SOL 在 4h/12h、ADA 在 4h 只有 90%；唯一不显著的是 SOL 的 8h）。

**⚠ 决定性的那个数字（原文逐字）：**
> **「滞后订单流分量在各期限上稳定贡献 5 到 6 个基点，
> 而公开信号分量从 4 小时的不足 1 个基点增长到 8 小时和 12 小时的
> 9.8 和 16.9 个基点。」**

- 这些是**四分位间效应**（从 25 分位移到 75 分位的预测收益变化，遵循 Boehmer et al. 2021）。
- 贡献份额（4h）：滞后流 **58%** [34, 65]、公开信号 **20%** [12, 49]、残差 **22%** [12, 30]。
  12h 时公开信号份额升到 **65%** [41, 77]。

> **对照本项目的 35 bps 往返成本：4h 的效应小了 6–7 倍。
> 连 12h 的 16.9 bps 也不到成本的一半。**
>
> **⚠ 不要把各分量的份额加权求和**——作者报告的是份额，不是一个总和。

**成本：完全没有。** 全文没有交易成本、手续费、价差或盈亏平衡的任何假设。
它报告的是预测斜率，不是 P&L。

**他们自己的稳健性检验：** 去掉嵌套交互项；分开正负失衡项；
用失衡的符号替代失衡值；Hodrick (1992) 标准误；
剔除 00:00/08:00/16:00 资金费结算刻钟（**结果不变，不是资金费的假象**）；
单独吸收整点交互（不变）。

**他们自己承认的弱点：**
> 10 秒开盘收益预测的平均 **R² 只有 3.4%、AUC 0.60**。
> **在任何成本下都不可交易。**

### 与本仓库的交叉印证（这是它最重要的价值）

| 测量 | 毛效应 | 成本 | 比值 |
|---|---:|---:|---:|
| 本仓库 5m 因子扫描（9 币，3.47M 根 bar） | **2.47 bps** | 12.0 bps | 0.21× |
| Kim & Hansen（6 币，毫秒级，4h 期限） | **5–6 bps** | — | — |

> **两个完全独立的仪器，测的是同一个家族，结果在同一数量级，
> 且都远低于成本。**
> **这比本仓库自己的扫描更有力地说明「成交量尖峰」家族已被测干**——
> 因为它是外部的、用了重叠修正的推断、
> 并且有一个**同时保留序列依赖与跨资产依赖的联合移动块 bootstrap**。

---

## 2. 扣除成本的加密永续信号：一个**空白**，不是一个来源

三个候选，全部有缺陷：

**(a) Bysik & Ślepaczuk (2026-05-19).** "Machine Learning-Based Bitcoin Trading
Under Transaction Costs: Evidence From Walk-Forward Forecasting."
**arXiv:2606.00060, 预印本.** https://arxiv.org/abs/2606.00060
- 约 70,000 个小时观测，2018–2026，XGBoost/LSTM/iTransformer，27 折 walk-forward。
- **有成本**：原文「一旦施加**十个基点**的交易成本，天真的符号策略就失效」。
- 缺陷：(i) **单资产 BTC**，没有分散；(ii) 每个正面结论都限定「在**选定的配置**下」，
  这是对配置网格的选择却被当成结果；(iii)「bootstrap 证据不支持形式上的统计优势」；
  (iv) 10 bps 低于本项目 35 bps 的压力档；
  (v) **无法核实是现货还是永续**——摘要只写「hourly BTC-USDT」。

**(b) Huang, Fan, Hu & Ye (2026-04-29).** "From Hypotheses to Factors:
Constrained LLM Agents in Cryptocurrency Markets." arXiv:2604.26747, 预印本.
- 原文：「只在 2020-2022 数据上训练、岭组合的等权多空组合，
  在 **2024-2026 纯样本外**期间取得 **44.55% 年化收益、Sharpe 1.55**，
  扣除**每边 5 个基点**的交易成本。」
- **致命缺陷：Table 1 是按「纯样本外 Sharpe」给 25 个因子排序的**——
  因子是按它们的样本外表现挑出来的。这是直接的样本外选择泄漏，
  **「纯样本外」这个标签撑不住**。
- 有用的一句：「市值加权版本表现很差，说明**alpha 集中在小币且受容量限制**。」

**(c) ⚠ 一条高价值指针，指向本仓库已经拥有的论文。**
`CARRY_LIT_REVIEW_2026-09-26.md` 记录了 He, Manela, Ross & von Wachter
**"Fundamentals of Perpetual Futures"（arXiv:2212.06888）**，
其中 **Table 8 是独立的费用-价差表，Table 6 是零成本部分**。
**⚠ 但本仓库引用的一直是零成本的 Table 6。v7 日期 2026-09-17，晚于 2026-09-26 的评审。**
**下一步：直接调 Table 8。**

---

## 3. 波动率管理/regime 条件（新增一篇同行评议，且它本身是空结果）

> **Grobys, Kolari, Sandretto, Shahzad & Äijö (2025).
> "Cryptocurrency momentum has (not) its moments."
> *Financial Markets and Portfolio Management* 39(4).
> doi:10.1007/s11408-025-00474-9. 2024-11-28 接收，2025 发表。**同行评议。**
> https://link.springer.com/article/10.1007/s11408-025-00474-9

**品种：现货，不是永续。** CoinMarketCap 日收盘 + 市值，USD。
每年 12 月重选市值前 30（89 个币），周频，30 天跳一天形成期五分位排序，
等权零成本多空。**2016-01 → 2023-12，416 个周度观测。**

**成本：不包含。** 通读方法、结果与结论，全文没有任何交易成本假设。
唯一的周转/成本提及（Barroso-Santa-Clara 的可比周转、「避免高交易成本」）
出现在**关于美股的文献综述里**，不是这个策略。

**逐字数字：**
- 朴素动量全样本 **0.90%/周**，作者自称 **"an insignificant average raw payoff"**。
- 2016-01→2020-07 子样本 **1.74%/周，「仅在 10% 水平名义显著」**。
- 2020-07→2023 **事后子样本为负且不显著**。
- **2020 年 12 月：组合单月崩了 −255.23%。** 原因是
  **「空头腿里某一个加密货币的价格极端跳空」**，不是市场反转。
- **剔除这一个观测，周均值升到 1.51%/周，t = 2.63（1% 水平）。**
- 波动率管理版：**1.86%–2.40%/周** 对 0.90%/周。

**为什么这是告诫而不是线索——三条，全部出自论文自己的文字：**
1. **它自己的附录推翻了标题。** Table 11 的市值加权风险调整回归，
   截距为 **−0.0106 (t = −1.25)、−0.0083 (t = −1.42)、−0.0095 (t = −1.63)**，
   负且不显著。显著的是对朴素动量的载荷（0.0034***, t = 11–17）。
2. **方差在数学上未定义。** 原文「该策略的方差由幂律指数 α < 3 推出，
   **在统计意义上未定义**」，其风险「与棉花价格变动或风险投资相当」；
   且「风险管理的加密动量**并未显著改变尾部风险**」。
   **一个方差未定义的序列上的 Sharpe，不是你能拿来交易的目标。**
3. **一个观测占复利收益的 37%**，30 个币里 1 个就能造成 −255% 的月份。

---

## 4. 爆仓级联：又一篇已发表的空结果（直接影响 SHARK-07）

> **Garcia Seuma, Ramon Marc (2026-07-29).** "Where does the criticality live?
> Early-warning signals are event-heterogeneous across seven crypto-perpetual
> liquidation cascades." **arXiv:2607.27070, 预印本.** https://arxiv.org/abs/2607.27070

2022–2025 年 7 次 BTC 级联，含 2025-10-10 创纪录的 190 亿美元那次；
分钟级价格 + 5 分钟杠杆/订单流，Kendall tau，每变量每事件 39 种配置。

**结论是负面的：**
> **"No variable is event-invariant."**
> 「价格在七次事件中的五次携带临界慢化特征，但在恰好两次突发新闻（关税）冲击中沉默。」
> 唯一在所有事件上都有数据的规律是**吃单订单流方差的压缩**，
> 它通过了 300 次起点安慰剂检验（Fisher 合并 **p ≈ 5e-6**），
> **但是「一个总体层面的前兆，不是一个逐事件的警报」**。
> 结论：「加密衍生品中单事件的临界慢化主张，**在构造上就是脆弱的**。」

> **对本项目的含义：SHARK-07 目前记为「TESTABLE, NULL so far」。
> 这篇是它「逐事件预警」前提上的一个已发表的空结果。**
> 成本不适用（不是交易论文）。

---

## 5. 2025–2026 加密永续系统化策略

> **Zhu, Linsen & Cai, Mengqing (2026-09-04).**
> "Artificial Intelligence in Equity and Crypto Markets: Progress, Profitability
> Evidence, and the Limits of Automated Investing."
> **arXiv:2609.04917, 预印本.** https://arxiv.org/abs/2609.04917

32 页综述，文献截止 2026-08-31，明确覆盖「中心化加密现货、永续合约」。
结论逐字：
> **"Within the public evidence examined here, no general AI architecture is
> shown to deliver persistent, cross-regime, capacity-aware net alpha."**
核心主张 C4：「现有公开证据不足以确立来自 AI 的、跨 regime、扣成本、可扩展的持续 alpha。」
它附带一个公开的 `claim_evidence_map.md`（主张/证据/反证对照表），
**是一个构建得不错的对抗性地图，值得读。**

**⚠ 2026-09-27 与 2026-09-28 两天内，各索引均无新论文。**
arXiv 自己的 feed（`updated 2026-09-27T22:40Z`）在这个方向上返回空。
**这一点应当明说：这两天没有新东西。**

### ⚠ 见到但**无法核实**——引用前必须先查

1. **Frontiers in Blockchain (2026-06-11)**
   "Microstructure alpha: hierarchical learning and cross-asset transfer in
   cryptocurrency markets", doi **10.3389/fbloc.2026.1811716**
   —— 声称同行评议、覆盖「六个主要加密货币在 Binance **现货与永续**上的
   超过三百万条分钟级观测」。**但页面是 JS 渲染的，正文一行都没取到。**
   **这是类别 1 剩下的最佳候选，值得手动用浏览器打开一次。**
2. Saluja, Srivastava et al., "Order Flow and Cryptocurrency Returns: A Machine
   Learning Approach with Out-of-Sample Validation", **SSRN 7055779 (2026-07-24)**, 预印本。
3. arXiv:2607.09230 "When Does Order Flow Matter? State-Dependent L2 Liquidity-State
   Transitions in Crypto Futures" (2026-07-10), 预印本。
4. arXiv:2602.00776 "Explainable Patterns in Cryptocurrency Microstructure", 预印本。
5. *Physica A*, "Order flow and cryptocurrency returns", S1386418126000029 (2026) — 403，未读。
6. arXiv:2608.03616 "Measuring the engine of a liquidation cascade" — 只在搜索摘要里出现，
   从未经 arXiv API 确认。

---

## 5b. 后续一（已完成）：He et al. v7 的**费用-价差部分**已取回并检验

> **He, Manela, Ross & von Wachter, "Fundamentals of Perpetual Futures",
> arXiv:2212.06888 v7, 2026-09-17**（预印本；2024 Utah Winter Finance Conference）
> 全文：https://arxiv.org/html/2212.06888v7

**本仓库的 carry 评审只引用了它的零成本部分（Table 6），却记录了费用-价差表
（Table 8）的存在。这次把原文取回来了，逐字如下：**

> **"for Bitcoin perpetual futures, the strategy generates a Sharpe ratio of 3.35
> under high trading costs typical of retail investors, and up to 11.65 for highly
> active market makers who pay no such fees. After additionally accounting for
> effective bid-ask spreads, the corresponding Sharpe ratios remain 3.27 and
> 10.46."**

**这是一个扣除手续费和真实买卖价差之后的结果，就在这家交易所上——本项目从未测过它，
因为它关的是「资金费超额」而不是「基差偏离」。**

**已在本项目数据上直接检验，结论是它不复现，且能说清为什么**：
见 `BASIS_ARBITRAGE_2026-09-28.md`。要点——基差被钉在无套利价 **±8.5 bps** 内，
**七天尺度上完全不回归**（46 个币的前瞻溢价变化 ≈ 0.0 bps），
而他们样本里偏离的波动是 52–90%/年、这里只有 **3.7%/年**。
**没有收敛就没有套利，与偏离幅度无关。**

> **教训：引用一个来源时必须确认你引用的是它的哪一部分。**
> 同一篇论文可以同时包含零成本和扣成本的结论，而它们可以指向相反方向。

---

## 5c. 后续二（已完成）：Pindza 2026 —— 一篇真正的**空结果**，而且是方法论范本

> **Pindza, Edson (2026). "Microstructure alpha: hierarchical learning and
> cross-asset transfer in cryptocurrency markets."**
> *Frontiers in Blockchain* 9:1811716, doi:10.3389/fbloc.2026.1811716.
> **同行评议，Original Research。** 2026-02-15 收稿，2026-05-18 接收，2026-06-11 发表。
> 全文（15 页，64k 字符）：
> https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/pdf
> （JS 页面取不到；`web_fetch` 不解析 `application/pdf`；
> 用 Python `requests` 拉 PDF + `pypdf` 提取成功。OpenAlex 的 GROBID XML 需 API key，401。）

**⚠ 标题承诺 alpha，论文交付的是空结果。摘要逐字：**

> **"gradient-boosted models overfit severely under proper leakage controls, and
> no strategy survives realistic exchange fees… microstructure signals carry
> genuine but weak information content that is useful for understanding market
> quality but not exploitable at standard retail fee levels."**

**这是本次检索中唯一一篇真正建模滑点的论文**，而且成本写得很干净：

> **"Round-trip costs are computed using Binance's published VIP-0 schedule:
> 10 bps per side for spot (20 bps round-trip) and 2 bps maker/5 bps taker for
> USDT-M perpetual futures (4-10 bps round-trip depending on execution assumptions).
> We additionally impose a conservative half-spread slippage equal to the
> contemporaneous Corwin-Schultz spread proxy."**

并且**自己列出遗漏项**：「abstracts from queue-position dynamics, funding-rate
costs on perpetual futures, borrow costs for short positions, and latency…
**The net Sharpe figures we report should therefore be read as an upper bound**」。

**结果（2025-08 → 2026-02，3,417,972 根分钟 bar，BTC/ETH/SOL/AVAX/LINK/DOT × 现货+永续，
purged walk-forward，k=5，5 分钟 purge + 60 分钟 embargo）：**

| 模型 | 毛 Sharpe | **净 Sharpe 现货** | **净 Sharpe 永续** | 周转 |
|---|---:|---:|---:|---:|
| AR(1) / 5 分钟动量 | 0.43 | **−31.29** | **−10.68** | 124× |
| OLS（微观结构） | **−0.31** | **−52.05** | **−18.42** | 203.8× |
| LightGBM | 0.96 | **−50.30** | **−16.98** | 201.9× |

**唯一没有被过拟合污染的模型（OLS）毛 Sharpe 本身就是负的（−0.31）**，
ΔR²_OOS 仅 +1.23%、DM 1.28、**p ≈ 0.20 不显著**；
**LightGBM 在 purged 样本外显著劣于随机游走（DM −6.83, p < 10⁻¹¹）。**

> **机制原句，正是本项目的问题：**
> **"at 20 bps per round trip on spot, 288 round trips per day generates
> cumulative costs that overwhelm any statistical edge by orders of magnitude."**

**引用时的三条告诫（都出自论文自己或可核对）：**
- **A. §5.3 自认的选样：**「a pilot version of the present paper」在**小时**频率上
  Amihud (0.43) 与 Kyle's λ (0.14) **未过 0.5 阈值**，然后改用**分钟**频率、
  **20 倍数据**重跑，12 个特征全过。作者自己说「all features pass does not
  imply that all carry economically meaningful information」。
  **这正是本仓库 `PREREG_1P5ATR` 记录过的「换了周期直到结果出现」。**
- **B. Table 4 与它自己的泄漏结论矛盾：** LightGBM 毛 Sharpe +0.96 是全表最好，
  但同一篇证明它的样本外预测**显著劣于随机游走**。**论文从未说明 Table 4 用的是哪个切分**，
  而那些毛数字看起来来自它自己 elsewhere 谴责的朴素 80/20。
- **C. 没有真正未被触碰的留出集**，12 个特征 12 次检验，**无多重检验校正**。

> **这不是一个「干净的样本外选择」违规者**——因为结果是空结果，空结果无法被选择抬高。
> **但如果引用它的方法，就把它当泄漏控制的模板；
> 引用它的毛 Sharpe 时必须带上 Table 4 的那条不一致。**

**对本项目的价值：**
1. **这是「加密微观结构在零售费率下不可交易」目前最干净的一条外部证据**，
   而它是**同行评议**的、成本写明的、**唯一真正建模滑点**的。
2. **它的 purge + embargo 做法可以抄进本项目的闸门。**
3. **它自曝的那次「换周期直到结果出现」，与本仓库的历史完全同型**——
   这是外部文献对本仓库方法论纪律的一个印证。

---

## 6. 非克隆的 freqtrade 策略，且方法论含滑点

> **这是一个结构性空结果：这个类别无法被满足。**
> freqtrade 的回测器没有滑点模型、没有市场冲击模型。
> 因此**任何在该引擎里运行的策略，其回测方法论在构造上就不可能包含滑点。**
> 任何声称「有记录在案且包含滑点的回测方法论」的 freqtrade 策略，
> 要么是假的，要么指的是一个外部包装器。

**作为完整性补充，最不寻常的非克隆策略：**
`darkvolg/Trading` — **"TrendRider"**，https://github.com/darkvolg/Trading
Bybit USDT 永续，13 个币对，1h，开源 GPL-3.0。
比 freqle 透明得多：**约 14 天的 walk-forward 留出、拒绝不能胜过基线的参数的验证闸门、
回滚并记录失败的超参运行、由机器人自己的 SQLite 驱动的实盘模拟盘面板。**

**但：**
- **不建模滑点**（记录的回测命令就是一条普通 `freqtrade backtesting`，没有 fee 或 slippage 参数）；
- **自 2026-04-01 起只做 $500 的模拟盘**；
- 它自己的 README 标题是 **「13 天保本交易」**；
- 回测窗口 20260104–20260423（约 3.6 个月）；
- 它是**一条获客漏斗**（招聘联系方式、付费层、Telegram 信号、50+ 篇 SEO 博客）。

> **判词：作为可复现性练习有意思，作为边界的参照毫无价值。**
> 其余浮现的仓库（horustechltd、titouannwtt、kiploks）都是 fork 或集成包装器，
> 没有已发表的方法论。

---

## 7. 对本项目的净结论

1. **不存在同行评议的、扣除成本的、日内/日频加密永续信号，其效应量足以覆盖成本。**
   **把这作为「发现」写进评审，而不是当成还没找到。**
2. **在恰好是本项目期限（4h）上，最佳的原始永续测量是每个四分位间 5–6 bps。**
   本项目自己的扫描测到 2.47 bps。**两者一致。**
3. **不要指望从文献里拿到 10 倍的效应量，因为文献里没有。**
   诚实的读法是：这对**搜索策略**是一个空结果，不是一个可以靠更多搜索填上的缺口。
4. **两个便宜的后续动作（都在内部）：**
   (a) 调出 **He et al. v7 (2026-09-17) 的 Table 8**（费用-价差表）——
   本仓库引用的一直是零成本的 Table 6；
   (b) 用浏览器手动打开 **Frontiers in Blockchain** 的 microstructure-alpha 那篇。
