# 量化回测陷阱与验证方法论 · 严谨清单

> 适用场景：美股日频、约 100 只流动大盘股 + ETF、2010–2026。
> 目标：**避免自欺**。优先覆盖"产出自信的错误正收益"的失败模式。
> 标注约定：**【定论】** = 有权威共识或可机械验证；**【判断】** = 取决于策略/渠道，属裁量。

---

## 0. 一句话总纲

最危险的不是策略弱，而是**信息集、选择过程、执行条件比真实交易者当时能拿到的更有利**。
回测应被当作**历史市场回放系统**，而不是 `strategy(清洗后的完整表)`。

| 环节 | 常见研究做法 | 生产级做法 | 扭曲方向 |
|---|---|---|---|
| 数据 | 最新数据覆盖历史 | PIT / 双时间戳快照 | 收益↑ |
| 股票池 | 今天还活着的票 | 当时可投资universe | 收益↑、回撤↓ |
| 时间切分 | 随机 K-fold | walk-forward / purged CV | 泛化↑ |
| 调参 | 看了测试集再改 | trial ledger + 锁定 holdout | Sharpe↑ |
| 统计 | p<0.05 即接受 | BH/Bonferroni、PBO、DSR | 显著性↑ |
| 执行 | close-to-close、零成本 | 延迟 + 成交 + 价差 + 冲击 | 收益↑ |

---

## 1. Look-ahead / Survivorship Bias

### 1.1 Survivorship bias 的量级

**【定论】** 用"今天的 S&P 500 成分股"回测历史，是**结构性、静默、方向确定**的正偏。

直接实测（同一 low-P/E 价值策略，2000–2025，103 个季度，两组 universe 对照）：

| 指标 | 有偏（今天成分股） | 无偏（PIT 成分股） | 偏差 |
|---|---|---|---|
| CAGR | 13.74% | 11.96% | **+1.78%** |
| Sharpe | 0.619 | 0.478 | **+0.141** |
| Max Drawdown | −42.2% | −49.3% | **隐藏 7.1pp** |
| Sortino | 0.961 | 0.726 | +0.235 |
| 期末价值($10k) | ~$275k | ~$183k | +$92k |

关键洞察：**风险端的扭曲比收益端更严重**。有偏回测声称只承担 66.7% 的市场下跌，真实是 77.8%（down capture）。偏差集中在危机期：Q4 2008 有偏 −15.89% vs 无偏 −20.86%（单季 5pp 差）；Q1 2020 −40.22% vs −45.32%（5.10pp）。

**学界与业界量级共识**：
- 朴素股票回测：**约 1–2% / 年**（小盘、新兴市场、共同基金universe更大）。
- Brown, Goetzmann, Ibbotson & Ross (1992) 共同基金：约 **+0.66pp/年**。
- Dimensional 测 1991–2020 美股主动基金：中位 alpha 被高估 **0.60%/年**（−1.44% → −0.84%）。
- 宽基指数实务界常引 **1–3% / 年**。

### 1.2 更隐蔽的第二层：delisting return bias

**【定论】** **"包含退市股"不等于已修正 survivorship。** Shumway (1997) 发现 CRSP 中因破产等负面原因退市的股票**普遍缺失正确的退市收益**，被忽略的终值损失很大。只用"最后可得收盘价"会**低估**最坏情形的损失。

落地要求：
```python
# 历史 universe 必须由当时状态决定
eligible = securities[(listed_at <= d) & (delisted_at.isna() | (d < delisted_at))]
# 体检：历史 universe 中后来退市的比例接近 0 → 重大警告
future_delist_rate = eligible["delisted_at"].notna().mean()
```
退市收益（`ret` × `dlret`）的合成公式**不要跨数据版本盲目套用**，须遵循数据发布文档。

### 1.3 如何量化/披露（无法修正时）

**【判断】** 若买不起 PIT 数据，最小合规做法：

1. **A/B 对照**：用今天成分股 vs 你能构造的最近似历史名单各跑一次，报告
   `ΔSR = SR_survivors − SR_PIT`、ΔCAGR、ΔMaxDD、Δalpha，并给出 bootstrap CI。
2. **明示折扣**：在报告里直接写"CAGR 减去 1–2%/年作为 survivorship haircut"。
3. **持仓归零压力测试**：问"若组合中 2–3 只票归零会怎样"。有偏回测隐藏了这个场景，无偏回测显示 25 年里发生过多次。
4. **标明 universe 性质**：若回测是"今天的 AAPL/MSFT/GOOG…"，那是**这个 basket 的研究**，不是策略。

### 1.4 Point-in-time 数据的成本与近似

**【判断】** 真实可得选项：

| 来源 | 内容 | 成本量级 |
|---|---|---|
| **Norgate Data** | 美股 survivorship-bias-free；Platinum = 日线回溯至 1990 + **退市股** + **历史指数成分**；Diamond = 回溯至 1950 | 订阅制（Platinum/Diamond 档），按月/年 |
| **Sharadar** | 近 30 年美股基本面 + EOD 价格 + 公司行动 + securities master，**声明 PIT 且 survivorship-bias-free**；REST API 或批量下载 | 订阅制，相对便宜 |
| **CRSP / Compustat (WRDS)** | 学术金标准：含 active **与 inactive** securities、PERMNO 永久标识、delisting code/return | **订阅门槛（机构授权）**，个人基本不可得 |
| **SEC EDGAR** | 免费，含 filing 时间元数据（可自建 PIT 基本面） | 免费但工程量大 |

**低成本近似路径**：
- **价格/成分**：Norgate Platinum（唯一同时给退市股 + 历史成分的实惠选项）。
- **基本面**：自建 `event_time` / `available_at` 双时间戳，用 `merge_asof(direction="backward")` 做 as-of join，并 `assert (available_at <= decision_at).all()`。
- **10-K/10-Q 滞后**：财年结束后 **25–49 天**（均值 ~38 天）才到 EDGAR；大型加速申报人上限 60 天；13F 硬性 45 天。用 period-end join 或直接 ffill 最新值 = 把"尚未写出的报告"给了策略。
- **重述陷阱**：Plug Power FY2018 稀释 EPS 原报 −$0.36（2019-03 申报），2021-05-14 重述为 −$0.39。必须保留 `revision_id` / `valid_from` / `valid_to`（双时间存储）。

---

## 2. Walk-forward vs In-sample/Out-of-sample

### 2.1 为什么单一 70/30 切分不够

**【定论】** 单一 split 是**一个点估计**。把边界挪一个月，OOS 结论可能从 +38% 变 −12%：

```
Split 1: 训练到 2025-09 → OOS +38%
Split 2: 训练到 2025-06 → OOS -12%
Split 3: 训练到 2025-12 → OOS  +7%
```
三次切分三个结论，**没有一个可信**。必须用**连续多段**的系统性检验。

### 2.2 正确的三层结构

**【定论】** 生产级协议：

```
Development train  →  Time-aware validation / inner CV  →  Frozen final OOS "vault"
```

```python
cut1, cut2 = pd.Timestamp("2022-01-01"), pd.Timestamp("2025-01-01")
train      = df[df.index < cut1]
validation = df[(df.index >= cut1) & (df.index < cut2)]
final_oos  = df[df.index >= cut2]   # 不参与任何模型选择
```

**核心纪律**：OOS 一旦被看过并据此改过指标/阈值/universe，**它就已经变成 IS**。White (2000) 指出：反复使用同一段历史做模型选择，本身就会制造偶然的赢家。

### 2.3 Walk-forward 协议

**【定论】** 每个窗口：**在 `[t0, tk]` 上拟合 → 冻结 → 在完全未见的 `(tk, tk+H]` 上交易 → 前移**。最终只拼接 **OOS** 段计算指标。

| 模式 | 训练窗 | 优点 | 缺点 |
|---|---|---|---|
| **Anchored（扩展）** | `[t0, tk]` 持续增长 | 估计更稳；早期模式不丢 | 旧数据"稀释"当前 regime；耗时增长 |
| **Rolling（滚动）** | `[tk−W, tk]` 定长 | 适应 regime 漂移；耗时恒定 | 样本少、参数方差大；W 本身可被过拟合 |

**参数建议（【判断】，日频股票）**：
- 训练窗应含 **≥200–300 笔交易**（或至少覆盖多轮 regime）。
- 测试窗 = 训练的 **20–33%**；测试窗不能短到成为噪声。
- 训练窗重叠建议 **50%**（窗口数 vs 估计独立性之间的平衡）。
- **OOS fold 数量**：不要设固定数字，要保证每个 fold 含足够交易与市场状态；通常 **≥8–12 个 OOS fold** 才有分布可看。若样本不够，改用 CPCV（见 2.4）。
- 切片**必须用交易日历**，不能用行数（停牌、IPO、时区会破坏"252 行 = 1 年"）。

### 2.4 避免"OOS 只是另一个 IS"

**【定论】** 四条硬规则：

1. **嵌套验证**：调参只在外层训练集内部做 inner CV；外层只评估"整个调参流程"的泛化。经典错误是在全样本上选特征/调超参再"walk-forward"。
2. **Trial ledger（试验账本）**：自动记录**每一次**回测运行（含被丢弃的）。N 不能靠记忆。
3. **Purge + Embargo**（见 2.5）。
4. **锁定 vault**：最终 OOS 只在最后跑一次。跑第二次就要在报告里声明。

**警惕**：walk-forward **不能**发现 look-ahead。泄漏在 fold 之间是一致的，所以能通过 walk-forward 并表现为"宽阔的参数高原"而非尖峰。

### 2.5 Purged K-Fold + Embargo（含重叠标签时）

**【定论】** 样本 $i$ 的信息区间 $I_i=[t_{i,0}, t_{i,1}]$（持有期内正向窗口）。若 $I_i \cap I_j \neq \varnothing$，训练样本 $i$ 必须被**清除（purge）**。额外在测试块**之后**加一个缓冲 **embargo**：

$$h_{\text{embargo}} = \lceil \delta T \rceil \quad (\delta \sim 1\%)$$

- purge 长度由**标签时域**决定；embargo 由**残差自相关 + 特征回看 + 执行时域**决定 —— 不是"别人用 5 天我也用 5 天"。
- **失败模式**：只 purge 不 embargo（序列相关仍泄漏）；embargo 相对自相关长度过小；标签区间记错；**全样本预处理**（scaler/PCA 必须在 fold 内拟合）；把 CPCV 的多条路径当独立（它们共享数据、彼此相关）。

**CPCV（Combinatorial Purged CV）**：把 T 分成 N 组，取全部 $\binom{N}{k}$ 种测试组合，purge+embargo 每一组 → **一条净值曲线变成一族曲线/分布**，直接用于估 PBO。副作用：路径不独立，估方差时要注意。

---

## 3. 多重检验 / p-hacking

### 3.1 核心机制

**【定论】** 在固定历史上搜索 N 个配置 = 取 N 个噪声数的**最大值**。即使所有策略真实 edge 为零：

$$\mathbb{E}\big[\max_N t\big] \approx \sqrt{2\ln N}$$

N=1000 时 ≈ **3.7** —— 一个"统计显著"的 t 值，纯由运气产生。

### 3.2 门槛该用多少

| 门槛 | 数值 | 说明 |
|---|---|---|
| 教科书 t 检验 | \|t\| > 2.0 | **对因子研究远远不够** |
| **Harvey, Liu & Zhu (2016)** | **t > 3.0** | 针对"已经有很多人试过"的现实；并非每策略固定分数线，而是多重检验严重性的警示 |
| Bonferroni (FWER) | α/m | 100 次检验、α=0.05 → 每次 **0.0005**。很保守，适合少量关键的 go/no-go |
| Benjamini-Hochberg (FDR) | 最大 k 使 $p_{(k)} \le \frac{k}{m}q$ | 比 FWER 有功效 |

**注意**：喂给多重检验程序的原始 p 值本身必须合理 —— 策略收益序列相关、策略间高度相关，硬套 IID t 检验会出错（应用 HAC / block bootstrap）。

**有效独立试验数**：50 个 lookback 变体（相邻窗口相关 >0.9，远距离 ~0.2）→ 有效试验数可能只有 **4–5**。用原始 N=50 修正会过度惩罚；完全不修正则严重低估。应**从实际试验的相关矩阵估计**。

### 3.3 Probabilistic Sharpe Ratio (PSR)

**【定论】** 给定观测 Sharpe，真实 Sharpe 超过基准 $SR^\*$ 的概率：

$$\widehat{PSR}(SR^*) = \Phi\!\left(\frac{(\widehat{SR}-SR^*)\sqrt{n-1}}{\sqrt{1-\hat\gamma_3\widehat{SR}+\frac{\hat\gamma_4-1}{4}\widehat{SR}^2}}\right)$$

- $\hat\gamma_3$ 偏度、$\hat\gamma_4$ 峰度、$n$ 观测数。频率必须一致（日频 Sharpe 配日频 n）。
- **示例**：月度 SR=0.30、n=36。正态 → PSR **0.96**（过 0.95）；若 skew=−0.5、kurt=6 → PSR **0.94**（**跌破 0.95**）。收益路径没变，只是形状变了，结论就翻转。
- 负偏 + 厚尾（卖期权、carry、做空波动率）会**放大标准误**。
- PSR **不知道你试了多少次** —— 高 PSR 的单策略回测仍在隐藏选择偏差。

### 3.4 Deflated Sharpe Ratio (DSR)

**【定论】** DSR = **基准被替换为"多重检验下的期望最大 Sharpe"** 的 PSR。

期望最大 Sharpe（Bailey & López de Prado Eq.1）：
$$E[\max\{\widehat{SR}_n\}] = E[\{\widehat{SR}_n\}] + \sqrt{V[\{\widehat{SR}_n\}]}\cdot\big((1-\gamma)Z^{-1}[1-1/N] + \gamma Z^{-1}[1-1/(Ne)]\big)$$
其中 $\gamma \approx 0.5772$（Euler–Mascheroni）。零假设下 $E[\cdot]=0$，阈值塌缩为 $\sqrt{V}$ 项。

**论文自身的例子（记住这张表）**：年化 Sharpe **2.5**、5 年日频（T=1250）、skew **−3**、kurt **10**：

| 情形 | 独立试验数 N | DSR | 判定 |
|---|---|---|---|
| 如所报告 | **1000** | **≈0.90** | **失败**（<0.95） |
| 试验更少 | **46** | **0.9505** | 通过 |
| 若收益正态 | 最多 88 | 恰在线上 | 通过 |

→ 同一个 2.5 的 Sharpe，N=46 可信、N=1000 不可信。**非正态单独就扣掉一半额度**。

**最难也最关键的输入是 N**。N 不是"你保存了几个策略"，而是**你试了多少次** —— 包括每次参数扫描、每个被丢弃的变体、每个"我再试一个过滤器"。低报 N 是最容易给自己贴金的方式。

> 操作规则：**数清每一次试验，对期望最大值做通缩，DSR < 0.95 一律视为未证明** —— 无论原始 Sharpe 多漂亮。

### 3.5 最小回测长度 MinBTL

**【定论】** 给定试了 N 个变体，一段回测要多长，"幸运的最大值"才不会自动达到你宣称的 Sharpe：

$$\text{MinBTL} \approx \frac{2\ln N}{\overline{SR}^{\,2}} \ \text{年}$$

（精确版用 N 个高斯最大值的 Gumbel 表达；经验法则对小 N 略偏保守。）

| 试验数 N | 目标 SR=1.0 所需年数（精确） |
|---|---|
| 5 | ~1.4 |
| 10 | ~2.5 |
| 45 | ~5.0 |
| 100 | ~6.4 |
| 500 | ~9.3 |
| **1000** | **~10.6**（经验法则 13.8） |
| 1,000,000 | ~23.7 |

**读法**：45 个变体只是"一个诚实的周末迭代"，已经吃掉 5 年日频数据。N 从 10 → 1000 大致**三倍化**所需数据量。

**工作示例**：N=500、5 年数据、最优 SR=1.4 → MinBTL ≈ 6.3 年 > 5 年 → **样本短于最低要求**，红牌先于一切后续检验。

**陷阱**：只统计最后一个网格（N 应是完整搜索史，含非正式试验）；把 N 当独立（相关变体像更少的有效试验，但这不是忽略它的借口）；把 MinBTL 当充分条件（它只是**必要**条件）；忘记非平稳性（更长也意味着更旧的 regime）。

### 3.6 PBO（回测过拟合概率）via CSCV

**【定论】** PBO 估计的是：**IS 选出的最优配置，在 OOS 落到较差一半的概率**。

流程：把 $T \times N$ 收益矩阵按时间切成 S 个连续块 → 枚举全部 $\binom{S}{S/2}$ 种对称 IS/OOS 划分 → 每次取 IS 最优者，记录其 **OOS 相对排名** $\bar\omega_c$ → 取 logit $\lambda_c = \ln(\bar\omega_c/(1-\bar\omega_c))$ → 

$$\text{PBO} = \Pr[\lambda_c < 0] = \frac{1}{\binom{S}{S/2}}\sum_c \mathbb{1}[\lambda_c<0]$$

- **PBO ≈ 0.5**：IS 排名对 OOS 毫无信息 → 纯过拟合。
- **PBO < 0.1**：IS 技能确实会延续。
- 工作示例：20 配置、504 日、S=8（70 种划分）→ PBO **45.7%**，IS 冠军的 OOS 中位 SR **−0.06**。
- **不要**把 PBO 变成"调到通过为止"的另一个门槛。低 PBO 是必要的安慰信号，不是充分条件。

---

## 4. Transaction Costs & Capacity（美股大盘，2024–2026）

### 4.1 显性成本（几乎可以忽略）

| 项目 | 数值 | 备注 |
|---|---|---|
| 零售佣金 | **$0** | 2019 年后主流券商零佣金；IBKR Fixed 约 $0.005/股（有最低/最高） |
| **SEC Section 31 fee（卖出）** | **$0.00 / 百万美元**，自 **2025-05-14** 起 | 此前 $27.80/百万。**【定论】** |
| **FINRA TAF（卖出）** | **$0.000166 / 股，每笔上限 $8.30** | 执行价低于费率时不收 |

→ 对**小账户**，显性成本量级是"忽略不计"。**真正的成本是隐性成本。**

### 4.2 隐性成本：价差与冲击

**【定论】** Frazzini, Israel & Moskowitz 用近/超万亿美元 live 成交数据测：
- **大盘股平均市场冲击 = 11.21 bps**；小盘 = 21.27 bps。
- 结论：真实交易成本**不到**许多文献假设的十分之一；value 与 momentum 比 size **更可扩展**；短期反转受成本约束最重。

**【判断】** 实务量级（日频、零售/小账户）：

| 证券类别 | 典型价差 | 1% ADV 时的冲击 |
|---|---|---|
| **S&P 500 大盘** | **1–3 bps** | **2–5 bps** |
| Russell 2000 小盘 | 5–15 bps | 10–30 bps |
| 新兴市场大盘 | 10–30 bps | 15–50 bps |
| 微盘（<$300M） | 30–100+ bps | 50–200+ bps |

**平方根冲击律**（跨数千种工具稳健）：
$$I(Q) = Y \cdot \sigma \cdot \sqrt{\frac{Q}{V}}$$
其中 $\sigma$ 为日波动率、$V$ 为日成交量、$Y$ 为 order-unity 前置因子（典型 0.5–1）。性质：**凹性**（次线性）。

**为什么大盘股策略里冲击基本无关**：小额账户的交易量对个股 ADV 的占比极小，$\sqrt{Q/V}$ 极小。**只有当 AUM 增长到单票单日交易量占到 ADV 的显著比例时才成为约束。** 具体容量需自己算：对 $Y=0.5$、$\sigma_{daily}=2\%$，若要冲击 < 5 bps，则 $\sqrt{Q/V} < 0.05$，即 $Q/V < 0.25\%$ ADV。若单票日成交 $500M，则单日该票上限约 $1.25M。

### 4.3 做空成本（若做空）

**【判断】**
- **Easy-to-borrow** 大盘股：约 **0.5–1% / 年**（general collateral）。
- **Hard-to-borrow**：**10–50%+ / 年**。
- **可用性 survivorship**：回测里"能借到"的假设会系统性偏向于**当时容易借的、后来表现好的**票。真实做空组合受 borrow availability 约束。
- **短边不对称**：短腿成本更高、有挤空风险、且收益分布左偏。

### 4.4 有据可查的"成本杀死异象"

**【定论】** McLean & Pontiff 研究 **97 个**已发表异象：组合收益 **样本外低 26%**，**发表后低 58%**，其中 **32%（=58−26）**归因于 publication-informed trading。样本外下降是 data mining 效应的上界。
**【定论】** Novy-Marx & Velikov：**高换手策略的成本（在完全无视成本设计时）总是超过 1%/月**；成本对多数异象显著超过毛价差；最有效的缓解技术是 **buy/hold spread**（建仓要求严于持仓要求）。

### 4.5 如何在日频回测里"正确地"建模成本

**【定论】** 六条：

1. **两条腿都要收费**。价差在**买入和卖出**各付**半个价差**。只收一次是常见的低估。
2. **对"变动的部分"收费，不是对全部 notional**。再平衡只交易 delta：
   ```python
   trade_notional = abs(target_weight - current_weight) * portfolio_value
   cost = trade_notional * (half_spread_bps + impact_bps) / 1e4
   ```
   经典 bug：对 `target_weight * portfolio_value` 收费 → 换手被系统性高估，或反过来只用毛换手忽略净额。
3. **不要在收盘价既成交又 mark**。成交用次日开盘（或保守用次日收盘），mark 用收盘。同一收盘价建仓并 mark = 零成本入场幻觉。
4. **"先跑零成本再减成本"的谬误**：成本改变路径依赖（止损/信号随后变化），不是常数扣除。年化拖累 ≈ 年换手 × 单腿成本。10–20x/年换手 × 10bps ≈ **1–2%/年**；× 50bps ≈ **5–10%/年**。有案例 gross Sharpe 3.0 → net 1.0。
5. **做成本敏感性**：至少跑 **0.5× / 1.0× / 1.5× / 2.0×** 成本乘数 + 流动性冲击 + ADV 参与率上限。
6. **算盈亏平衡成本（break-even cost）**：
   $$c_{BE} = \frac{\text{每轮毛 P\&L}}{\text{每轮交易 notional}}$$
   然后问"现实成本有多大概率保持在 $c_{BE}$ 以下"。这比单点净收益稳健得多。
   - 策略 X：毛 8bp、成本 5bp、净 3bp → 需成本上涨 **60%** 才亏。
   - 策略 Y：毛 20bp、成本 17bp、净 3bp → 只需上涨 **18%** 就亏。
   **两者净收益相同，但安全边际完全不同。**

**【判断】给你的具体建议**：美股流动大盘股 + ETF、小账户、2024–2026，
**单边 3–6 bps（含半个价差 + 少量摩擦），往返 6–12 bps** 是忠实且偏保守的区间。
若策略含小盘或高换手，提到单边 10 bps。**并对 2× 做压力测试** —— 若 edge 在 2× 成本下消失，它从来就不是真的。

---

## 5. 应伴随每次回测的统计检验

### 5.1 Sharpe 的标准误（Lo 2002）

**【定论】** IID 假设下：
$$\text{SE}(\widehat{SR}) \approx \sqrt{\frac{1+\widehat{SR}^2/2}{T}}$$
**年化后几乎是白送的简单式**：
$$\boxed{\text{SE}(\widehat{SR}_{\text{annual}}) \approx \frac{1}{\sqrt{N}},\quad N=\text{年数}}$$

**这是最重要的一句**：**年化 Sharpe 的误差棒 = 1/√年数，与其他无关。** 更高频数据只给你更多行，不给你更多关于"年度风险收益比"的信息。

**工作示例**：3 年、Sharpe 1.5。
- SE = 1/√3 = 0.577；t = 1.5/0.577 = **2.60**（过 1.96，5% 显著）。
- 95% CI = **1.5 ± 1.96×0.577 = [0.37, 2.63]**。
- "显著"和"估得准"是两件事：你排除了零，几乎没排除别的。
- 若只有 1 年：SE=1.0，t=1.5，CI = **[−0.46, 3.46]** —— 毫无信息。

**所需记录长度**：$\widehat{SR}/\text{SE} > 1.96 \Rightarrow N > (1.96/SR)^2$ 年。

| 真实 Sharpe | 所需年数 |
|---|---|
| 0.3 | 43 |
| 0.5 | 15 |
| 1.0 | 3.8 |
| 1.5 | 1.7 |
| 2.0 | 1.0 |

**厚尾修正（Mertens）**：
$$\text{Var}(\widehat{SR}) = \frac{1+\tfrac12 SR^2 - \gamma_3 SR + \tfrac{\gamma_4-3}{4}SR^2}{T}$$
**示例（5 年月度，T=60，月度 SR=0.30 → 年化 1.04，skew=−1.5，kurt=8）**：
- 朴素：t = **2.27**（显著）
- 修正：t = **1.83**（**不显著**）
→ 偏度+峰度贡献了方差的 **1/3 以上**，直接翻转结论。

### 5.2 序列相关：Lo 的自相关调整

**【定论】** 标准 **√q 年化假设收益不相关**。正自相关使波动被低估 → 年化 Sharpe 被**高估**。

$$\eta(q) = \frac{q}{\sqrt{q + 2\sum_{k=1}^{q-1}(q-k)\rho_k}}$$

**Lo 的实证结论**：由于月度收益的序列相关，**对冲基金的年化 Sharpe 可被高估多达 65%**；负自相关则相反（低估）。调整后基金排名会变化。

**判断量级**：月度一阶自相关 ρ₁ ≈ 0.3–0.4 会把年化 Sharpe 抹掉约 **20–30%**（1.04 → ~0.75–0.85）。

> 注意：对**流动日频大盘股**，这个效应通常远小于对冲基金（后者因非流动持仓被 stale mark 平滑）。**但你要先算一下自己策略收益的自相关，而不是假设它不存在。**

### 5.3 Bootstrap / Block Bootstrap（路径依赖）

**【定论】** 有闭式标准误，但假设正态独立 —— 真实策略有厚尾、偏度、自相关。Bootstrap 绕开分布假设。

**关键**：**必须用 block bootstrap**（或 Politis–Romano stationary bootstrap），不能逐日独立重采样 —— 后者抹掉自相关结构，**低估不确定性**，给出"看起来令人安心但其实是假的"窄区间。

- **块长**：等于策略典型持有期的若干倍；通过"块长继续增大时 bootstrap 方差是否稳定"来校验。太短退化为 IID；太长则剩余独立块太少，区间因错误原因变宽。
- **重复次数**：**10,000** 是实用默认。少于 1,000 时，置信带依赖的尾部只由少数极端路径估出，每次运行都会跳。
- 工具：`arch.bootstrap.StationaryBootstrap` + `optimal_block_length`（Politis–White 自动块长选择）。

**实测对照（同一 SR 估计）**：

| Bootstrap 方法 | 95% CI |
|---|---|
| IID 逐日 | [0.61, 1.21] |
| 5 日块 | [0.42, 1.27] |
| Stationary | [0.35, 1.31] |
| Regime 分层块 | [0.24, 1.26] |

→ **一旦保留时间依赖，区间比 IID 假设下更宽。** 这就是 IID bootstrap 在骗你。

**工作示例（3 年日频、年化 SR=1.4、10,000 次、块长 20 日）**：点估计 1.40，2.5% 分位 **0.58**，97.5% 分位 **2.19**，区间宽 **1.61**。同样的 1.4 若有 5 年历史，区间收窄到约 **[0.85, 1.95]**。同样的头条数字，可信度完全不同。

**Null 对照（很实用的自查）**：把同样波动率但**零真实 edge** 的收益序列（打乱均值的零假设序列）跑同一套 bootstrap。若零假设序列的区间与真实策略区间大幅重叠 → 技能证据很弱。

**路径依赖策略**：重采样**相关的完整状态单元**（position、return、spread、cost 必须保持对齐），而不是只打乱最终 PnL 序列。否则 bootstrap CI 会抹掉真实的执行依赖。

### 5.4 如何检验"显著跑赢 buy-and-hold"

**【定论】** 三个层次，从弱到强：

1. **对 benchmark 的 Sharpe 做 PSR**：把 $SR^\*$ 从 0 换成 buy-and-hold 的 Sharpe —— 这比问"是否有任何 edge"严格得多，所需长度显著变长。
2. **Jobson–Korkie–Memmel 检验**：检验两个 Sharpe 之差是否为零，**正确计入两者的相关性**（同期间交易的两策略收益很少独立；忽略相关性会低估"共同噪声"）。|z| < 2 一般意味着差异可能是噪声。**注意**：1.4 与 1.1 在同一 5 年样本上通常**统计上无法区分**。
3. **White's Reality Check / Hansen's SPA**（比较整个搜索集 vs 基准）：
   - 检验复合零假设"**没有任何**模型跑赢基准"，对**最大值**统计量建模，从而为多重性定价。
   - **Reality Check**：$T_{RC} = \max_k \sqrt{n}\,\bar f_k$，$f_k$ = 相对基准的损失差。
   - **SPA**：$T_{SPA} = \max_k \frac{\sqrt{n}\bar f_k}{\hat\omega_k}$ —— 学生化 + 剔除明显劣势模型（数据依赖阈值），**更有功效、更不被劣质模型拖累**。
   - 零分布用**stationary bootstrap**（几何分布块长）构建。
   - **前提**：必须保留并重测**你试过的每一个**规则，不只是最终候选。悄悄排除早期失败的尝试会使检验失效。

**回归法**：直接把策略收益对基准收益回归，对 **α 的 t 统计量**做检验（可加 HAC 标准误）。这是"是否显著跑赢"最直接的表述之一。

---

## 6. 静默放大收益的编码 Bug

> 本节是最高优先级。这些 bug 的特征是：**跑得通、不报错、数字漂亮**。

### 6.1 执行时点的 off-by-one（危害最大，【定论】）

**canonical rule**：信号用截至 T 日收盘的数据计算 → 最早可成交价是 **T+1 的 open**（保守可取 T+1 close）。T 日收盘价在 T 日收盘前不可知 → T 日 close 已被"花掉"。

**受控实验的硬数字**（4000 条合成历史、已知 ground truth、**零真实 edge**）：

| 管道 | Null（无 edge） | 真实有 edge |
|---|---|---|
| **诚实**（T 信号 → T+1 成交） | **−0.74** | **+1.57** |
| **同一根 bar 成交** | **+14.79** | +15.85 |
| 指标偷看 1 根 bar | +4.76 | +6.62 |
| 全样本标准化（sign 规则） | −0.84 | +1.46 |

→ **一个 off-by-one 把"正确亏损的纯噪声"变成"年化 Sharpe 14.79"。这是编造，不是偏差。**

**剂量响应（最重要的一张表）** —— 你不需要完整的 off-by-one：

| 捕获信号 bar 的比例 f | Null Sharpe | 真实 edge 情形 |
|---|---|---|
| 0.00（诚实） | −0.74 | +1.57 |
| **0.25** | **+3.90** | +6.41 |
| 0.50 | +9.86 | +12.20 |
| 1.00 | +14.79 | +15.85 |

**假上线率**（门槛 = 年化 Sharpe ≥ 1.0，零 edge 下）：同日成交 **68%**；指标偷看 **99.9%**；全样本标准化 12%。
→ 轻微乐观的滑点估计、或 intrabar 止损用"触发那根 bar 的 low"来检查，就足以落入 25% 那一档。

**pandas 的正确/错误写法**：
```python
pos  = signal.shift(1)      # ✅ 推荐：pos[t] = 在 t 日持有的仓位
pnl  = pos * ret            # ret = close.pct_change()

ret    = close.pct_change()
signal = (close > close.rolling(50).mean()).astype(float)
pnl    = signal * ret       # ❌ 同日：signal 含今日 close，ret 也是今日
```
**关键区别**：`shift(1)` 作用在 **position/signal** 上是对的；作用在 **returns** 上语义不同（`ret.shift(1)` 配 `signal` 是反向偷价）。

**实数据量级**（同信号、同收益序列）：5 根手工可验收益上同日 **+21.26%** vs 滞后 **−14.50%**；真实数据 50 日均线规则同日 **1162.54%** vs 滞后 **58.61%** vs buy&hold 165.45%（**滞后版跑输持有**）。

> **最快的自检：one-bar shift test。** 把所有成交推迟一根 bar。若业绩崩塢或翻号，你一直在交易过去。**这是全文最有价值的单一诊断，请写成单元测试。**

### 6.2 NaN 制造幽灵信号（【定论】）

**IEEE 754 语义**：`np.nan > x`、`x > np.nan`、`np.nan > np.nan` **全部返回 False**；只有 `!=` 返回 True。

**你已踩的坑，机制如下**：
```python
ma_fast = close.rolling(20).mean()   # min_periods 默认 = 20 → 前 19 行 NaN
ma_slow = close.rolling(50).mean()   # 前 49 行 NaN
raw     = (ma_fast > ma_slow)        # NaN 比较 → False，被静默吞掉
sig     = raw.astype(int)            # ✅ 不报错（已是 bool），NaN 变成 0
cross   = sig.diff()                 # 0 → 1 被记为"金叉"
```
两类幽灵信号：
1. **fast 有效、slow 仍 NaN** 的区间：真实 fast>slow 却记 0。
2. **slow 首次变有效那天**：比较变 True → 造出一个不存在的 0→1 金叉，回测在"均线策略首个可评估日"**凭空建仓**。

**为什么没报错**：`(ma > ma)` 返回 **bool** Series（NaN 已被比较吞掉），所以 `.astype(int)` 合法。若直接 `ma_fast.astype(int)` 会抛 `IntCastingNaNError` —— **比较先于 astype 发生**，这才是静默的根源。

**其他 NaN 通道**：
- **`fillna(0)`**：价格序列填 0 → 读成 −100% 崩盘；收益序列填 0 → 读成"无盈亏"，人为抹平缺口波动（尤其在停牌期）。
- **`dropna()` 静默移 index**：A `dropna()` 后取 `.values` 与未 dropna 的 B 相乘 → 按**位置**错位，全表平移。更隐蔽：非随机缺失（承压/停牌时正好缺）→ 删行本身就是 survivorship 的近亲。
- **`rolling` 的 `min_periods` 默认 = window**，不是 1。
- **`pct_change()` 的历史默认变更**：老 pandas 默认 `fill_method='pad'`（先 ffill 再算），2.1 起弃用、新版默认 `None`。**升级 pandas 会静默改变历史回测数值**。
- **零价 → `inf`**：`0 → x` 的 `pct_change` 给 inf，`cumprod` 后整条曲线变 inf/NaN。

**防御性写法**：
```python
WIN_F, WIN_S = 20, 50
ma_fast = close.rolling(WIN_F, min_periods=WIN_F).mean()
ma_slow = close.rolling(WIN_S, min_periods=WIN_S).mean()
valid   = ma_fast.notna() & ma_slow.notna()          # 显式有效性掩码
pos     = pd.Series(np.nan, index=close.index)
pos[valid] = (ma_fast[valid] > ma_slow[valid]).astype(int)
pos     = pos.shift(1)                               # 唯一的滞后点

valid_prev = valid.shift(1, fill_value=False)        # 交叉两端都须有效
golden = valid & valid_prev & (pos == 1) & (pos.shift(1) == 0)

ret = close.pct_change(fill_method=None)
ret = ret.replace([np.inf, -np.inf], np.nan)
assert (ret.abs() < 0.5).all()
assert pos.index.is_unique and pos.index.is_monotonic_increasing
assert len(pos.dropna()) == int(valid.sum())         # NaN 没有被吞掉
```
优先用 nullable dtype `astype("Int64")`，让 NaN 保持可见。

### 6.3 复权价格的前视陷阱（subtle，【定论】）

**机制**：CRSP 标准规定 **adjustment base date 通常取"最后一个有原始价格的日子"**，更早价格按该日之后发生的**全部事件**换算 → **backward adjustment**。

- **split factor** = T 之后每个 split 的 `split_to/split_from` 连乘。机械重述，**几乎无前视**（split 在生效日可见）。
- **dividend factor** = T 之后每个除息日的 `(P_cum − D)/P_cum` 连乘（每个因子 ≤ 1，越往前越小）。**这是纯回溯变换**：每来一笔新股息，**整段历史被重新缩放**。
- backward-adjust factor = dividend factor ÷ split factor。

**实证（SPY）**：2021-01-04 的 adj close，在 2022-05-04 取到 **362.7802**，在 2022-06-18 取到 **361.2233** —— 只因 2022-06-17 派了 $1.576871。整段历史被平移约 0.43%。

**含义**：今天下载的 adj close ≠ 当年屏幕上看到的；**同一回测 5 年后重跑，历史信号会变**。

**什么被扭曲、什么没有**：
- **没被扭曲**：两点之间的**比值/收益率**。任意区间内，后端点之后的股息因子会同时约掉 → `pct_change`、波动率、基于收益的统计**不受影响**。这就是"用 adj 算收益"正确的原因。
- **被扭曲**：任何**绝对价格水平**。back-adjust 把历史价格压低，于是：
  - 固定百分比止损被触发得太早/太晚；
  - **最低价筛选**（如">$5"剔除 penny stock）在历史上剔除了根本没到过该价位的票；
  - 按**固定股数/整手**成交的规模在历史上偏大；
  - 按**股数计佣金**被低估。

**正确约定（务必分开）**：
```python
ret_pnl  = adj_close.pct_change()                 # PnL：总收益序列（含股息再投资）
px_level = raw_close                              # 价格水平规则 / 股数 / 整手 / 每股佣金
px_level = raw_close / cumulative_split_factor    # 或：split-only，连续且无前视
```
**股息不要重复计**：
- 用 **adj_close** 算 PnL → 股息已内含，**不要再单独加股息现金流**（double count）。
- 用 **raw close** 算 PnL → **必须**在除息日加回股息，否则每年少算 ~1–2%（美股大盘股息率）。

**reverse split / penny / survivorship 组合陷阱**：反拆股（1-for-10）让 adj 历史价格被放大约 10 倍。若同时按"最低价 > $5"筛选，你会**保留**那些历史上是 penny stock、今天因反拆股看起来像正经价的票 —— 并**自动剔除真正退市的输家**。这是 survivorship 与复权误差的乘性叠加。

### 6.4 其他静默放大器

| # | Bug | 机制 | 检查 |
|---|---|---|---|
| a | **未 groupby 的 shift/pct_change** | 拼接面板边界穿越：每个 ticker 首行 = 上一 ticker 末行的"收益" | `groupby(level="ticker")` 后再 shift/pct_change/rolling |
| b | **Duplicate index** | `pd.concat` 重叠日期 → `pct_change` 给 0 收益 | `df[~df.index.duplicated(keep="last")]` + `assert index.is_unique` |
| c | **Warm-up 期计入统计** | 前 N 天指标无效却计入年化/Sharpe/MaxDD，把空窗当低波动期 → 抬高 Sharpe | 先 `df = df.loc[first_valid_index():]` 再算指标 |
| d | **close 同时做 fill 和 mark** | 同一收盘价建仓并 mark = 零成本入场幻觉 | fill 用次开、mark 用收盘 |
| e | **固定金额仓位忽略流动性** | 冲击 ∝ √(size/ADV) | 加 ADV 参与率上限 |
| f | **Timezone / resample 标签** | `label="left"` 用 bar **开盘**时间戳标记；在该时间戳下单 = 假设收盘前就能行动 = look-ahead | 用 `label="right", closed="right"`；先 `between_time("09:30","16:00")` 剥离盘前盘后 |
| g | **Ticker 复用** | 同一 symbol 在不同年代属于不同公司，按 ticker 索引把两家拼成一条"连续"历史且不报错 | 用永久标识符 join（CRSP **PERMNO** / CUSIP），ticker 只当显示标签 |
| h | **基本面 ffill 泄漏** | 用 period-end join 或直接 ffill 最新值 = 把尚未写出的报告给了策略 | 双时间戳 + `merge_asof` |
| i | **Corporate action gap** | 未复权价遇 5-for-1 拆股 → 假 −80% 收益 | volume 同样要调 |
| j | **Integer division / float** | `//` 算股数或权重；`volume.astype(int)` 截断 | 复利用 `np.exp(np.log1p(r).cumsum())`，`(1+ret).cumprod()` 一旦出现 −1 就永久归零 |
| k | **Halt / ffill 停牌** | stale 价格 = 零波动 + 零收益 → long 永不被 mark down、short 永不被 mark up → 系统性利好 long | 建 halt calendar：停牌日不可交易，恢复日一次计入完整 gap |
| l | **预处理/归一化前视** | 全样本 z-score / min-max / winsorize / PCA | 见下方重要说明 |

**关于 (l) 的重要澄清（【判断】，反直觉）**：受控实验显示，**泄漏的量级取决于泄漏进入决策的"通道"**：
- 若策略**只用特征的符号**（零阈值），全样本标准化几乎**零膨胀**（−0.74 → −0.84）—— 标准差缩放不改变符号。
- 一旦权重或阈值依赖特征的**幅度**（按 z-score 定仓位、非零阈值、神经网络输入），就开始**显著膨胀**。

实务报告预处理前视通常 **+0.3–0.5 Sharpe**（有案例 1.8 → 1.2）。**不要过度推广"标准化是安全的"结论** —— 要针对自己的通道去测。

### 6.5 "一天前视值多少 bps"

**【判断，非定论】** 没有单一权威数字 —— 完全取决于信号与同日收益的相关性。
若相关 ρ、日波动 σ，则同日成交每天多捕获 **ρ·σ**。美股大盘 σ_daily ≈ 1.5%，ρ 只要 0.05 就是 ~7.5 bps/天 ≈ **19%/年**。
→ **上面那张 Sharpe 剂量响应对照表，比任何通用"bps/年"数字更可信。请在自己的策略上测。**

### 6.6 落地 Checklist（针对 100 只票 + 2010–2026）

1. **单一滞后点**：只在 `pos = signal.shift(1)` 处滞后；全代码搜索 `signal * ret`。
2. **one-bar shift test 写成单元测试**，业绩崩塌即失败。
3. 所有 rolling **显式 `min_periods`**；所有比较先建 `valid` 掩码；断言 NaN 数不因运算减少。
4. 面板全部 `groupby(level="ticker")` 后再 shift/pct_change/rolling；`assert index.is_unique`。
5. **三套价格并存**：`raw_close`（水平规则/股数/整手）、`split_only`（连续水平）、`total_return`（PnL）。**永不用 adj_close 做阈值。**
6. PnL 用 raw → 除息日加回股息并断言年化股息率 ≈ 1–2%；用 adj → 不加股息。
7. `assert (ret.abs() < 0.5).all()` + `replace([±inf], nan)`。
8. **halt calendar**：停牌日不可交易，恢复日一次计入完整 gap。
9. 指标统计从 `first_valid_index()` 开始；报告样本量、Sharpe 置信区间、换手率、成本敏感性。
10. **记录数据快照日期与 pandas 版本** —— 否则今天和 5 年后的回测不可比。

> **建议优先实现第 1、2、4、5 条为可执行单元测试**（合成数据 + 已知 ground truth），因为这几类恰好是"跑得通、不报错、数字漂亮"的那一批。

---

## 7. 超越 Sharpe/CAGR 的脆弱性指标

### 7.1 为什么单看胜率会误导

**【定论】** 胜率完全不含盈亏幅度信息。两个组合可以胜率相同而期望天差地别。

$$\text{Expectancy（期望值）} = (\text{WinRate} \times \text{AvgWin}) - (\text{LossRate} \times \text{AvgLoss})$$

$$\text{Profit Factor（盈亏比）} = \frac{\text{总盈利}}{\text{总亏损}} = \frac{\text{WinRate} \times \text{AvgWin}}{\text{LossRate} \times \text{AvgLoss}}$$

- **Profit Factor > 1.5** 视为稳健 edge；**> 2.0** 优秀（【判断】，经验阈值）。
- 高胜率 + 小赢大亏 = 典型的"卖期权"型左偏分布 —— **Sharpe 看起来很好，但尾部风险致命**，而且标准误被严重低估（见 5.1 Mertens 修正）。
- 报告**期望值（以 R 为单位）** 与 **按交易数加权的样本量**，并给 bootstrap 区间。

### 7.2 综合统计套件（建议随每次回测一并输出）

| 统计量 | 回答什么问题 | 阈值/读法 |
|---|---|---|
| **Sharpe + 95% CI**（含 Mertens 修正） | 这个 Sharpe 估得准吗 | 报告区间，不只报点 |
| **PSR** | 真实 Sharpe 超过基准的概率 | < 0.95 未证明 |
| **DSR** | 计入试验次数后的同一问题 | **< 0.95 一律视为未证明** |
| **MinBTL** | 我的回测够长吗 | 样本 < MinBTL → 红牌 |
| **MinTRL** | 单条记录够长吗 | SR 1.0 正态需 5.1 年；skew −1/kurt 6 需 9.8 年 |
| **PBO (CSCV)** | IS 冠军在 OOS 会掉到中位以下吗 | ≈0.5 = 掷硬币；< 0.1 良好 |
| **White RC / Hansen SPA** | 整个搜索集里有人真跑赢基准吗 | 对多重性定价 |
| **Jobson–Korkie–Memmel** | 两个 Sharpe 的差是真的吗 | 计入相关性；1.4 vs 1.1 通常不可区分 |
| **Lo 自相关调整 Sharpe** | 我的收益有序列相关吗 | 正自相关 → 高估（基金可达 65%） |
| **Block bootstrap CI** | 非正态下的不确定区间 | 块长 = 持有期倍数；≥10,000 次 |
| **Break-even cost** | 成本上升多少会杀死策略 | 与 2× 成本情景对比 |

### 7.3 子期间 / Regime 稳定性

**【定论】** 单一全样本 Sharpe 会**平均掉**整个区间内发生的一切，包括策略完全失效的某个 regime。

**两个全样本 Sharpe 都是 1.0 的策略**：
- **策略 M（稳定）**：滚动 12 个月 Sharpe = 1.1, 0.9, 1.0, 1.2, 0.8, 1.1, 0.9, 1.0, 1.1 —— 围绕 1.0 窄幅波动。
- **策略 N（衰退）**：滚动 = 2.4, 2.1, 1.8, 1.0, 0.3, −0.2, −0.4, −0.1, 0.1 —— 从强劲滑向负值。

→ 对"是否配置资本"而言，**这是两个完全不同的情形**，而单点数字无法区分。

**应检查的三种形态**：
1. **滚动 Sharpe 持续下行** → 真实的 alpha 衰减（越来越多人发现并交易掉同一 edge）。
2. **突然的 regime 断裂**（好 → 平/负）→ 结构性变化（市场 regime、交易所规则、拥挤事件），而非渐进衰减。
3. **高方差无趋势** → Sharpe 估计只是噪声大，全样本数字本身不一定错，但不确定性很宽。

**其他稳健性检查**：
- **参数高原 vs 尖峰**：最优参数周围的值也应不错。
  ```
  好：  0.8 0.9 0.9        危险： 0.1  0.2  0.1
        0.9 1.0 0.9               0.2  2.4  0.0
        0.8 0.9 0.8               0.1 -0.1  0.2
  ```
- **起止日期敏感性**：挪动回测起止各几个月，结论是否翻转。
- **子期间分解**：按牛/熊/横盘、按十年、按波动率 regime 分别报告。
- **跨市场/跨资产复制**：同一逻辑在别的市场是否也成立（最强的防过拟合证据之一）。
- **IS–OOS gap**：报告 IS 与 OOS 的 Sharpe 差，而不是只报 OOS。
- **Walk-Forward Efficiency Ratio**：

  $$\text{WFER} = \frac{\text{PnL}_{OOS}}{\text{PnL}_{IS}}$$

  | WFER | 解读 |
  |---|---|
  | > 0.8 | 极佳稳健性，参数可迁移 |
  | 0.5–0.8 | 可接受，但有衰减 |
  | 0.3–0.5 | 边界，可能部分过拟合 |
  | < 0.3 | 过拟合 |
  | < 0 | OOS 亏损 —— 完全过拟合或逻辑错误 |

  **WFER < 0.5 作为主要过滤器。**

---

## 8. 优先级总结：最会骗你的失败模式

按"产生自信的错误正收益"的严重程度排序：

| 排名 | 失败模式 | 典型量级 | 检测手段 |
|---|---|---|---|
| **1** | **执行 off-by-one / 同日成交** | null Sharpe −0.74 → **+14.79**；仅 25% 剂量 → +3.90 | **one-bar shift test** |
| **2** | **多重检验（未披露 N）** | N=1000 时 t≈3.7 纯靠运气；Sharpe 2.5 的 DSR 仅 0.90 | DSR / MinBTL / PBO / trial ledger |
| **3** | **指标偷看**（centered MA、`filtfilt` 零相位） | null → **+4.76**；99.9% 假上线率 | 逐个指标问"最高读到哪个 index" |
| **4** | **Survivorship bias** | **+1.78% CAGR、+0.141 Sharpe、隐藏 7.1pp 回撤** | A/B 对照 + delist rate 体检 |
| **5** | **成本被忽略/低估** | 高换手异象成本 **>1%/月**；200–400 bps/年 | Break-even cost + 2× 压力测试 |
| **6** | **复权价格前视** | 价格水平规则被扭曲；股息因子回溯缩放 | 三套价格分离；raw 用于阈值 |
| **7** | **NaN 幽灵信号** | 首个有效日凭空建仓 | `valid` 掩码 + 断言 |
| **8** | **单一 split 的 OOS** | 挪边界即翻号（+38% → −12%） | Walk-forward + CPCV + 锁定 vault |
| **9** | **Sharpe 未报区间** | 3 年 SR 1.5 → CI [0.37, 2.63] | SE = 1/√N + Mertens + bootstrap |
| **10** | **发表后衰减** | 97 异象：OOS −26%、发表后 −58% | 横截面复制检验 |

---

## 9. 主要来源

**回测过拟合 / 多重检验**
- [Bailey & López de Prado — The Deflated Sharpe Ratio (JPM 2014)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
- [Bailey, Borwein, López de Prado & Zhu — Pseudo-Mathematics and Financial Charlatanism](http://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf)
- [Bailey, Borwein, López de Prado & Zhu — The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253) · [eScholarship 全文](https://escholarship.org/uc/item/4w1110bb)
- [Harvey, Liu & Zhu — …and the Cross-Section of Expected Returns (RFS 2016)](https://www.nber.org/papers/w20592) · [PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF)
- [Quant Memo — Minimum Backtest Length](https://quantmemo.com/concepts/minimum-backtest-length) · [Backtest Overfitting](https://quantmemo.com/concepts/backtest-overfitting) · [Effective Number of Independent Trials](https://quantmemo.com/concepts/effective-number-of-independent-trials)
- [AlphaAssay — MinBTL 计算器与公式](https://alphaassay.com/research/minimum-backtest-length)

**Sharpe 统计推断 / Bootstrap**
- [Lo (2002) — The Statistics of Sharpe Ratios, FAJ](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios) · [JSTOR](https://www.jstor.org/stable/4480405)
- [Quant Memo — Standard Error of the Sharpe Ratio](https://quantmemo.com/concepts/sharpe-ratio-standard-error) · [Probabilistic Sharpe Ratio](https://quantmemo.com/concepts/probabilistic-sharpe-ratio) · [Lo's Autocorrelation-Adjusted Sharpe](https://quantmemo.com/concepts/lo-autocorrelation-adjusted-sharpe)
- [Quant Memo — Bootstrapped Confidence Bands for the Sharpe Ratio](https://quantmemo.com/concepts/bootstrapped-confidence-bands-for-sharpe) · [Jobson-Korkie-Memmel Test](https://quantmemo.com/concepts/jobson-korkie-memmel-test) · [White's Reality Check](https://quantmemo.com/concepts/white-reality-check)
- [Ledoit & Wolf — Robust Performance Hypothesis Testing with the Sharpe Ratio](https://www.ledoit.net/jef2008_abstract.htm)
- [Politis & Romano — The Stationary Bootstrap (JASA 1994)](https://doi.org/10.1080/01621459.1994.10476870)
- [Politis & White — Automatic Block-Length Selection for the Dependent Bootstrap](https://public.econ.duke.edu/~ap172/Politis_White_2004.pdf)
- [arch — Stationary Bootstrap 文档](https://arch.readthedocs.io/en/stable/bootstrap/timeseries-bootstraps.html)
- [Two Sigma — Sharpe Ratio: Estimation, Confidence Intervals, and Hypothesis Testing (PDF)](https://www.twosigma.com/wp-content/uploads/sharpe-tr-1.pdf)
- [Hansen (2005) — A Test for Superior Predictive Ability](https://www.tandfonline.com/doi/abs/10.1198/073500105000000063)
- [MetricGate — White Reality Check / Hansen SPA](https://metricgate.com/docs/reality-check-superior-predictive-ability/)

**Survivorship / PIT 数据**
- [Trading Studio — S&P 500 Survivorship Bias 实测 (+1.78% CAGR)](https://blog.tradingstudio.finance/sp500-survivorship-bias-backtest/)
- [QuanterLab — Survivorship Bias in Equity Backtests](https://quanterlab.com/articles/foundations-survivorship-bias)
- [Shumway (1997) — The Delisting Bias in CRSP Data](https://scholarsarchive.byu.edu/facpub/9278/) · [JSTOR](https://www.jstor.org/stable/2329566)
- [Brown, Goetzmann, Ibbotson & Ross (1992) — Survivorship Bias in Performance Studies, RFS 5(4)](https://doi.org/10.1093/rfs/5.4.553) · [Elton, Gruber & Blake (1996), RFS 9(4)](https://doi.org/10.1093/rfs/9.4.1097)
- [Norgate Data — 定价与数据内容](https://norgatedata.com/prices.php) · [数据内容表](https://norgatedata.com/data-content-tables.php)
- [Sharadar — PIT / survivorship-bias-free 美股数据](https://sharadar.com/) · [Fundamentals](https://sharadar.com/fundamentals)
- [IAR Wiki — WRDS / CRSP / Compustat: the paywalled core](https://instituteforautomatedresearch.org/wiki/commercial/wrds/)
- [ERNIE 技术报告 — Backtesting: From Research Bias to Production Reality（PIT、双时间戳、delisting）](https://ernie55ernie.github.io/trading/2026/08/27/backtest.html)
- [SEC EDGAR — Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)

**验证协议 / Walk-forward / Purged CV**
- [Quant Memo — Purged & Embargoed Cross-Validation](https://quantmemo.com/concepts/purged-embargoed-cv) · [Walk-Forward Analysis](https://quantmemo.com/concepts/walk-forward) · [Nested Cross-Validation](https://quantmemo.com/concepts/nested-cross-validation) · [Rolling Performance Windows](https://quantmemo.com/concepts/rolling-performance-windows-and-stability)
- [Marketmaker.cc — Walk-Forward Optimization: The Only Honest Strategy Test](https://marketmaker.cc/en/blog/post/walk-forward-optimization)
- [sklearn — TimeSeriesSplit](https://sklearn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) · [skfolio — WalkForward / CombinatorialPurgedCV](https://skfolio.org/generated/skfolio.model_selection.WalkForward.html)
- [White (2000) — A Reality Check for Data Snooping, Econometrica](https://doi.org/10.1111/1468-0262.00152)
- [López de Prado — Advances in Financial Machine Learning (Ch. 7, 11, 14)](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086)

**交易成本 / 容量 / 微观结构**
- [Frazzini, Israel & Moskowitz — Trading Costs of Asset Pricing Anomalies (PDF)](https://pages.stern.nyu.edu/~afrazzin/pdf/Trading%20Cost%20of%20Asset%20Pricing%20Anomalies%20-%20Frazzini,%20Israel%20and%20Moskowitz.pdf) · [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2294498)
- [Frazzini, Israel & Moskowitz — Trading Costs (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719)
- [Novy-Marx & Velikov — A Taxonomy of Anomalies and Their Trading Costs (RFS 2016)](https://www.nber.org/papers/w20721) · [PDF](https://www.nber.org/system/files/working_papers/w20721/w20721.pdf)
- [Almgren & Chriss — Optimal Execution of Portfolio Transactions](https://doi.org/10.21314/JOR.2001.041)
- [Square-Root Law of Market Impact（综述）](https://www.emergentmind.com/topics/square-root-law-of-market-impact)
- [QuanterLab — Transaction Cost Modeling: Spread + Impact](https://quanterlab.com/articles/diagnostics-transaction-cost)
- [Quant Memo — Transaction Costs](https://quantmemo.com/concepts/transaction-costs) · [Break-Even Transaction Cost Analysis](https://quantmemo.com/concepts/break-even-transaction-cost-analysis) · [Corwin-Schultz High-Low Spread Estimator](https://quantmemo.com/concepts/corwin-schultz-high-low-spread)
- [FINRA — Section 1 Member Regulatory Fees (TAF $0.000166/股, 上限 $8.30)](https://www.finra.org/rules-guidance/rulebooks/corporate-organization/section-1-member-regulatory-fees) · [Information Notice 4/24/25（Section 31 费率）](https://www.finra.org/rules-guidance/notices/information-notice-20250424)
- [SEC — Section 31 Transaction Fee Rate Advisory FY2025](https://www.sec.gov/rules-regulations/fee-rate-advisories/2025-2)
- [Interactive Brokers — Commissions & Fees](https://www.interactivebrokers.com/en/pricing/commissions-home.php)

**代码级 Bug / 复权价格**
- [Marketmaker.cc — Look-Ahead Bias: How a One-Bar Mistake Manufactures a Sharpe of 15 From Pure Noise（受控实验）](https://marketmaker.cc/en/blog/post/look-ahead-bias-taxonomy/) · [论文/代码](https://github.com/suenot/lookahead-inflation)
- [Portfolio Optimizer — Adjusted Prices Without Look-Ahead Bias（CRSP base date + SPY 实证）](https://portfoliooptimizer.io/blog/adjusted-prices-without-look-ahead-bias/)
- [BacktestGyan — Adjusted Prices（back-adjusted vs point-in-time）](https://backtestgyan.bulansarkar.com/data-quality/adjusted-prices) · [Missing Data](https://backtestgyan.bulansarkar.com/data-quality/missing-data)
- [Alexander Hübbert — Why do I lag the signal?（同日 vs 滞后实测）](https://alexanderhubbert.com/learn/python/lessons/advanced/30_lookahead.html)
- [pandas — DataFrame.pct_change（fill_method 默认变更）](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.pct_change.html)
- [StockFit — Point-in-Time Data（10-K 滞后、重述案例）](https://developer.stockfit.io/blog/point-in-time-data-backtesting)
- [Quant Memo — Ticker Recycling and Symbol Collisions](https://quantmemo.com/concepts/ticker-recycling-and-symbol-collisions)
- [Alphanume — Resampling Intraday Data With Pandas（label/closed 语义）](https://www.alphanume.com/blog/resample-intraday-data-pandas)
- [Ernest Chan — Backtesting and its Pitfalls（QTS Capital）](https://epchan.com/img/links/Backtesting-and-its-Pitfalls.pdf)

**发表后衰减 / 异象稳健性**
- [McLean & Pontiff — Does Academic Research Destroy Stock Return Predictability? (JF 2016)](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365) · [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623) · [JSTOR](https://www.jstor.org/stable/43869094)

**绩效指标**
- [TradeZella — Trading Expectancy](https://www.tradezella.com/blog/trading-expectancy)
- [MetricGate — Lo Autocorrelation-Adjusted Sharpe Calculator](https://metricgate.com/docs/lo-autocorrelation-sharpe/)
- [BacktestScore — Minimum Track Record Length（含表格）](https://www.backtestscore.com/minimum-track-record-length)
