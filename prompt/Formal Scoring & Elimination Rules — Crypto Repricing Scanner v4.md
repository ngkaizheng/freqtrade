# 50. Formal Scoring & Elimination System

这是整个研究框架的正式评分与淘汰系统。

核心原则：

> **先淘汰明显不成立的机会，再给剩余候选评分。**

绝对不能让：

- 高 Attention
- 高 Meme potential
- 高 Revenue
- 高 Catalyst

其中任何一个单项，掩盖：

- 严重 Supply Risk
- 严重 Liquidity Risk
- Security Risk
- 没有 Token Capture
- 已经完全 Priced In
- 没有真实 Information Gap

因此：

```text
Hard Veto
    ↓
Opportunity Archetype
    ↓
7-Dimension Score
    ↓
Evidence / Confidence Adjustment
    ↓
Market Regime Adjustment
    ↓
Final Score
    ↓
Status
```

---

# 51. Step 0 — Data Integrity Gate

在评分之前，先判断：

> **这个 candidate 是否有足够可靠的数据进行评分？**

关键数据包括：

- Market Cap
- FDV
- Circulating Supply
- Liquidity
- Catalyst
- Token Capture
- Revenue / Fees
- Unlock
- Attention
- Market Positioning

## Data Integrity Rules

### PASS

至少：

- 市场数据可以由可靠来源交叉验证
- 核心 thesis 至少有一个官方 / on-chain / high-quality source 支撑
- 关键数字没有影响结论的重大冲突

### DATA INSUFFICIENT

如果：

- Price / MC / supply 差异巨大
- Catalyst 只有 KOL 传言
- Buyback 无法确认是否执行
- Revenue 完全无法验证
- Liquidity 无法确认
- Token contract 身份存在冲突

则：

> **不得硬评分。**

Status：

**Data Insufficient**

---

# 52. Step 1 — Hard Veto Rules

任何 candidate 触发以下规则，都不得进入正常 Ranking。

## VETO-1 — No Identifiable Repricing Mechanism

如果无法回答：

> “为什么未来 30–90 天市场可能重新估值这个 token？”

则：

**Reject**

必须至少有一个明确 Driver：

```text
Fundamental
OR
Catalyst
OR
Attention
OR
Supply
OR
Liquidity
OR
Reflexivity
```

如果全部 ≤2/5：

> Reject

---

## VETO-2 — No Token-Level Exposure

如果 thesis 只有：

```text
Protocol grows
TVL grows
Users grow
Revenue grows
```

但：

```text
Token capture ≈ 0
```

而且没有：

- buyback
- burn
- staking income
- fee sharing
- token utility
- supply reduction
- direct demand mechanism

则：

> Reject the fundamental thesis.

注意：

这不代表 token 永远不会涨。

如果它拥有强烈 Attention / Meme / Reflexivity thesis，可以重新归类成：

> Attention Trade

而不是 Fundamental Trade。

---

## VETO-3 — Severe Security Risk

例如：

- 未解决 exploit
- Honeypot
- Admin 能任意铸币
- LP 可被无保护撤走
- 合约权限异常
- 明确 rug risk
- 关键升级权限高度集中且不可接受

且无法通过可靠来源解释：

> Reject

---

## VETO-4 — Non-Exitable for a $500 Position

我的典型仓位约 $500。

因此 candidate 至少需要满足：

### 基础流动性

通常要求：

```text
24h volume ≥ $250K
```

以及尽可能确认：

```text
可执行买入深度
+
可执行卖出深度
```

而不是只看 aggregated volume。

如果：

```text
24h volume 看起来很高
但
真实 order book / DEX liquidity 极低
```

则：

> Data Insufficient / Reject

取决于能否找到可靠的真实流动性数据。

对于特殊超小盘 Meme，可以放宽 volume 要求，但：

> 必须确认 $500 能进入，并且在合理冲击成本下退出。

---

## VETO-5 — Catastrophic Supply Shock

如果未来 30 天：

```text
Unlock > 50% circulating supply
```

并且：

- 无对应的大额需求事件
- 无 lockup
- 无吸收机制
- 无 buyback / burn 对冲
- 无明确市场 absorption evidence

则：

> Reject

未来 90 天：

```text
Unlock > 100% of current circulating supply
```

且没有足够吸收机制：

> Reject

这不是说大解锁一定 bearish。

而是：

> **没有解释机制的大解锁不能进入高优先级研究。**

如果解锁本身就是 thesis，例如：

```text
large unlock
+
historically absorbed
+
large new demand
+
major listing
+
revenue expansion
```

则允许进入特殊：

> Supply Absorption Trade

---

## VETO-6 — Completely Priced In

如果：

```text
Catalyst 已经发生
+
没有新的 follow-up information gap
+
价格已经大幅 rerating
+
Attention 已经极高
+
Volume 已经进入极端
```

则：

> Priced In

特别注意：

### 不允许使用：

> “距离 ATH 还很远”

作为未定价证据。

ATH distance 只是背景数据。

---

## VETO-7 — No Information Gap

如果：

```text
Market expectation
≈
Expected actual outcome
```

且没有明显：

> positive surprise potential

则：

> Reject / Weak

因为：

> Catalyst 本身不等于 opportunity。

---

# 53. Step 2 — Identify Opportunity Archetype

每个 candidate 必须先分类。

只能有一个 Primary Archetype，最多一个 Secondary Archetype。

## A. Fundamental Repricing

适合：

- DeFi
- Lending
- DEX
- Staking
- Fee-sharing token

核心：

```text
Revenue
→
Token Capture
→
Cash Flow / Buyback / Burn
→
Rerating
```

---

## B. Catalyst Repricing

核心：

```text
Known Catalyst
+
Market Expectation
<
Potential Actual Outcome
```

例如：

- Mainnet
- Upgrade
- Listing
- Buyback
- Revenue launch
- Tokenomics change

---

## C. Attention Repricing

核心：

```text
Attention Velocity
→
New Buyers
→
Liquidity
→
Price Discovery
```

---

## D. Meme / Reflexive

核心：

```text
Attention
+
Community
+
Liquidity
+
Reflexivity
```

Fundamental 可以非常弱。

---

## E. Supply Repricing

核心：

```text
Burn
+
Buyback
+
Reduced Emissions
-
Unlock
```

重点是：

> Net Supply Pressure。

---

## F. Hybrid

例如：

```text
Catalyst
+
Fundamental
+
Attention
```

通常最值得深入研究。

---

# 54. Step 3 — Seven-Dimension Score

每项：

> **0–5 分**

不得使用主观整数而不解释。

必须根据下面的定义给分。

---

# 55. Score A — Information Gap (G)

权重根据 Archetype 调整。

### 0

市场完全知道，事件已经发生，没有新的信息。

### 1

几乎所有关键变量已经被市场定价。

### 2

存在小幅未知因素，但不足以改变估值。

### 3

存在明确未知变量，可能影响重新定价。

### 4

存在：

```text
Quantifiable
+
Testable
+
Material
```

的信息差。

### 5

存在非常明确的：

```text
Current Market Expectation
vs
Potential Actual Outcome
```

而且差异足以改变 Token valuation。

---

# 56. Score B — Fundamental / Token Capture (F)

### 0

项目成功与 Token 无关。

### 1

只有弱 token utility。

### 2

有 token utility，但经济价值很小。

### 3

存在真实 Token Capture。

### 4

Token Capture 已经被实际数据验证，而且有增长空间。

### 5

Token 捕获机制：

```text
Direct
+
Large
+
Recurring
+
Scalable
```

例如：

- Revenue sharing
- Buyback
- Burn
- Staking cash flow

---

# 57. Score C — Catalyst Quality (C)

### 0

没有具体 Catalyst。

### 1

只是 roadmap / rumor。

### 2

有官方计划，但日期或执行不确定。

### 3

官方确认，有合理时间窗口。

### 4

官方硬日期 / 链上执行机制，而且经济影响明确。

### 5

```text
Hard Catalyst
+
Hard Date
+
Material Token Impact
+
Measurable Outcome
```

例如：

```text
Mainnet
→
Sequencer Revenue
→
Buyback
```

比：

```text
Partnership Announcement
```

得分高。

---

# 58. Score D — Attention / Narrative Velocity (A)

这里不看：

> “现在很热门。”

而看：

> **Attention 是否加速。**

### 0

Attention 快速衰退。

### 1

极低关注度且无增长。

### 2

稳定，没有明显变化。

### 3

7D / 30D attention 明显上升。

### 4

明显 acceleration：

```text
mentions ↑
engagement ↑
search ↑
volume ↑
holders ↑
```

多个指标同步。

### 5

出现明显 Attention Shock：

```text
Social Velocity ↑↑
+
Community Growth ↑
+
Search ↑
+
Volume ↑
+
New Buyers ↑
```

并且有证据表明不是纯机器人 / paid promotion。

---

# 59. Score E — Liquidity / Positioning (L)

### 0

无法正常退出。

### 1

极薄。

### 2

$500 可以交易，但明显有冲击。

### 3

足够支持小仓位正常进出。

### 4

流动性良好：

```text
Spot volume
+
Order book
+
DEX liquidity
```

相互一致。

### 5

深度很好，而且：

```text
Spot demand
+
Healthy OI
+
Funding not extreme
```

市场结构健康。

注意：

> Volume ≠ Liquidity。

---

# 60. Score F — Supply Quality (S)

### 0

严重稀释：

```text
Large unlock
+
Large emissions
+
No absorption
```

### 1

明显负面。

### 2

可接受但存在明显 dilution。

### 3

基本中性。

### 4

Supply pressure 较低：

```text
low unlock
+
manageable emissions
+
buyback
```

### 5

强烈有利：

```text
Burn
+
Buyback
+
Low unlock
+
Low emissions
```

造成结构性净供给收缩。

---

# 61. Score G — Reflexivity (R)

### 0

没有反身性。

### 1

很弱。

### 2

一般。

### 3

具有：

```text
Price
↔
Attention
```

反馈。

### 4

明显存在：

```text
Price ↑
→
Attention ↑
→
Liquidity ↑
→
New Buyers ↑
```

### 5

具有高度病毒传播潜力：

```text
Low / Mid MC
+
Strong Community
+
High Attention Velocity
+
Exchange Accessibility
+
Strong Liquidity
+
Narrative Reflexivity
```

主要适用于 Meme / consumer / speculative narratives。

---

# 62. Archetype Weighting

不要让所有 Token 使用同一权重。

## Fundamental Repricing

| Dimension | Weight |
|---|---:|
| Fundamental / Token Capture | 25 |
| Information Gap | 20 |
| Catalyst | 15 |
| Supply | 15 |
| Attention | 10 |
| Liquidity | 10 |
| Reflexivity | 5 |

---

## Catalyst Repricing

| Dimension | Weight |
|---|---:|
| Catalyst | 25 |
| Information Gap | 25 |
| Fundamental / Token Capture | 15 |
| Attention | 15 |
| Supply | 10 |
| Liquidity | 5 |
| Reflexivity | 5 |

---

## Attention Repricing

| Dimension | Weight |
|---|---:|
| Attention | 30 |
| Information Gap | 20 |
| Reflexivity | 20 |
| Liquidity | 15 |
| Catalyst | 10 |
| Supply | 5 |
| Fundamental | 0 |

---

## Meme / Reflexive

| Dimension | Weight |
|---|---:|
| Attention | 30 |
| Reflexivity | 25 |
| Information Gap | 20 |
| Liquidity | 15 |
| Catalyst | 5 |
| Supply | 5 |
| Fundamental | 0 |

---

## Supply Repricing

| Dimension | Weight |
|---|---:|
| Supply | 25 |
| Information Gap | 20 |
| Catalyst | 20 |
| Fundamental | 15 |
| Attention | 10 |
| Liquidity | 10 |
| Reflexivity | 0 |

---

## Hybrid

默认：

| Dimension | Weight |
|---|---:|
| Information Gap | 20 |
| Fundamental | 20 |
| Catalyst | 15 |
| Attention | 15 |
| Supply | 10 |
| Liquidity | 10 |
| Reflexivity | 10 |

---

# 63. Raw Score Calculation

每个维度：

```text
0–5
```

最终：

```text
Raw Score
=
Σ(
Dimension Score / 5
×
Dimension Weight
)
```

范围：

```text
0–100
```

例如：

```text
Information Gap = 4/5
Fundamental = 4/5
Catalyst = 5/5
Attention = 3/5
Supply = 3/5
Liquidity = 4/5
Reflexivity = 2/5
```

按 Hybrid 权重：

```text
Raw Score
=
16
+
16
+
15
+
9
+
6
+
8
+
4
=
74
```

---

# 64. Step 4 — Evidence Confidence Adjustment

Raw Score 不能直接使用。

根据证据质量进行调整。

## Confidence A

```text
On-chain
+
Official
+
Independent verification
```

调整：

> 100%

---

## Confidence B

主要是：

```text
Official
+
Protocol accounting
```

但链上尚未完全确认。

调整：

> 95%

---

## Confidence C

主要依赖：

```text
Official claims
+
Secondary confirmation
```

调整：

> 85%

---

## Confidence D

主要依赖：

```text
KOL
+
X speculation
+
Media
```

调整：

> 70%

---

## Confidence E

只有：

```text
Rumor
```

调整：

> 不进入正式排名。

Status：

**Data Insufficient**

---

# 65. Market Regime Adjustment

评分不是脱离市场环境的。

设：

```text
Regime Factor
```

范围：

```text
0.90
–
1.10
```

### Regime strongly supports thesis

：

```text
1.10
```

### Neutral

：

```text
1.00
```

### Regime mildly against thesis

：

```text
0.95
```

### Regime strongly against thesis

：

```text
0.90
```

例如：

Meme Mania 下：

> Meme / Reflexivity candidate

可能：

```text
1.10
```

但：

> Long-duration fundamental alt

可能：

```text
0.95
```

注意：

> Regime Factor 不能把一个坏 candidate 变成好 candidate。

它只能调整优先级。

---

# 66. Final Score

最终：

```text
Final Score
=
Raw Score
×
Evidence Factor
×
Regime Factor
```

最终范围仍然约：

```text
0–110
```

为了方便排序，也可以显示：

> Normalized Score = Final Score / 1.10

得到：

```text
0–100
```

---

# 67. Minimum Qualification Rules

一个 candidate 即使总分高，也必须满足：

## Rule A

至少一个 Primary Driver：

```text
F ≥ 4
OR
C ≥ 4
OR
A ≥ 4
OR
S ≥ 4
OR
R ≥ 4
```

## Rule B

Information Gap：

```text
G ≥ 3
```

否则：

> Reject / Weak

因为：

> 没有 information gap 就没有明确 repricing edge。

## Rule C

Liquidity：

```text
L ≥ 2
```

否则：

> Data Insufficient / Reject

## Rule D

Evidence：

必须：

```text
Confidence ≥ C
```

才能进入正式排名。

---

# 68. Final Status Thresholds

## 85–100

**Deep DD**

条件：

```text
Final Score ≥ 85
+
No Hard Veto
+
G ≥ 4
+
Primary Driver ≥ 4
+
Liquidity ≥ 2
+
Confidence ≥ B
```

---

## 75–84

**High-Priority Watch**

机会明显，但至少一个关键变量仍未确认。

例如：

```text
Catalyst strong
but
economic outcome unknown
```

---

## 65–74

**Watch**

有逻辑，但信息差还不够大。

---

## 55–64

**Speculative / Low Priority**

可能有交易性，但缺乏足够 evidence 或 repricing asymmetry。

---

## <55

**Reject**

除非存在特殊事件刚刚发生、数据明显滞后，否则不继续深入。

---

# 69. 特殊 Status 不由 Score 决定

以下状态直接覆盖 Score。

## Priced In

发生：

```text
Catalyst already realized
+
Market already rerated
+
Information Gap ≤ 2
```

则：

> Priced In

即使：

```text Score = 90
```

也不能列为 Deep DD。

---

## Data Insufficient

发生：

```text
Critical data unavailable
OR
Major unresolved contradiction
```

则：

> Data Insufficient

不能因为模型估计而补数字。

---

## Reject

发生：

```text
Hard Veto
```

则：

> Reject

Score 不重要。

---

# 70. Anti-Hype Rule

任何单一维度不得“劫持”整个评分。

例如：

```text
Attention = 5
```

不能因为：

> Meme 很热

就自动成为 Deep DD。

同样：

```text
Fundamental = 5
```

不能因为：

> Revenue 很高

就自动成为 Deep DD。

至少需要：

```text
Information Gap ≥ 3
```

以及：

```text
Primary Driver ≥ 4
```

---

# 71. Anti-Value-Trap Rule

如果：

```text
Fundamental = 5
```

但：

```text Attention ≤ 2
Catalyst ≤ 2
Information Gap ≤ 2
```

则：

> 不允许因为“便宜”而进入 Deep DD。

原因：

> Cheap can remain cheap.

---

# 72. Anti-Meme-Chasing Rule

如果：

```text
Attention ≥ 5
Reflexivity ≥ 5
```

但：

```text Information Gap ≤ 2
Liquidity ≤ 2
Supply ≤ 1
```

则：

> Reject

这防止：

> “因为它正在 pump，所以继续追。”

---

# 73. Anti-Catalyst-Chasing Rule

如果：

```text Catalyst = 5
```

但是：

```text Information Gap ≤ 2
```

则：

> Priced In / Watch

因为：

> Hard catalyst ≠ profitable trade.

---

# 74. Anti-10x Fantasy Rule

如果我要求：

> 5× / 10× / 20×

必须进行 Reality Check。

至少计算：

```text
Target MC
÷
Current MC
```

以及：

```text Required Fundamental Growth
```

或：

```text Required Attention / Liquidity Expansion
```

或：

```text Required Narrative Comparable
```

---

# 75. 5× Reality Check

例如：

```text
Current MC = $50M
5× = $250M
```

必须回答：

### Fundamental Route

需要：

```text
Holder Revenue
+
Required valuation yield
```

达到多少？

### Catalyst Route

需要：

```text
Catalyst economic impact
```

达到多少？

### Attention Route

需要：

```text
Social growth
+
Volume
+
Liquidity
+
Holder growth
```

增长多少？

### Meme Route

需要：

```text
Narrative comparable MC
```

达到什么级别？

---

# 76. 10× Reality Check

严格要求：

> 10× 不能只写“可能”。

必须说明：

```text
10× Current MC
```

意味着什么。

例如：

```text
Current MC = $80M
10× = $800M
```

必须至少有一个可信路线：

```text
Fundamental
OR
Catalyst
OR
Attention / Reflexivity
OR
Hybrid
```

如果全部都不成立：

> 10× scenario = unsupported

---

# 77. 20× Reality Check

20× 是 Extreme Case。

不得把：

> 20×

当 Base Case。

必须要求：

```text
Extreme scenario
+
credible mechanism
+
comparable precedent
```

如果没有：

> 只标记为 speculative mathematical scenario。

---

# 78. Thesis Invalidation Rules

评分不是买入之后就固定。

每次新数据出现，都重新计算。

## Fundamental Thesis Failure

例如：

```text
Revenue ↓ >30%
+
Holder Revenue ↓
+
Token Capture ↓
```

连续两期恶化：

> Downgrade

---

## Catalyst Failure

例如：

```text
Catalyst delayed beyond research window
```

则：

> Catalyst score = 0–1

重新计算。

---

## Attention Thesis Failure

例如：

```text
7D Attention ↓ >50%
+
Mentions ↓
+
Engagement ↓
+
New Holders ↓
```

则：

> Attention thesis invalidated

---

## Supply Thesis Failure

例如：

```text
Unlock materially larger than expected
+
Absorption absent
```

则：

> Supply score ≤1

---

## Liquidity Thesis Failure

例如：

```text
Liquidity ↓ >60%
```

或者：

```text
Depth collapses
```

则：

> Re-evaluate exit feasibility immediately.

---

# 79. Post-Catalyst Rule

Catalyst 发生以后，不允许继续使用旧 thesis。

必须重新比较：

```text
Expected
vs
Actual
```

然后重新计算：

```text
Information Gap
Fundamental
Attention
Liquidity
Supply
```

---

# 80. Post-Catalyst Repricing Rule

如果：

```text
Catalyst successful
+
Price ↑
+
Attention ↑
```

但：

```text Fundamental data
<
Market expectation
```

则：

> Sell-the-News Risk ↑

不能因为：

> Catalyst 成功

就自动继续 bullish。

---

# 81. Candidate Ranking Output

最终表必须额外增加：

| Token | Archetype | Raw | Final | G | F | C | A | L | S | R | Confidence | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|

其中：

```text
G = Information Gap
F = Fundamental / Token Capture
C = Catalyst
A = Attention
L = Liquidity
S = Supply
R = Reflexivity
```

---

# 82. 每一个 Top Candidate 必须显示“为什么得分”

不能只给：

```text
Score = 87
```

必须写：

```text
G 5/5 — market cannot price the first sequencer revenue yet
F 4/5 — direct token capture confirmed
C 4/5 — official launch window
A 3/5 — narrative known but not accelerating
L 4/5 — sufficient depth
S 2/5 — high FDV
R 4/5 — strong ecosystem reflexivity
```

这样评分才可审计。

---

# 83. Score ≠ Probability

必须明确：

> **Score 不是价格上涨概率。**

例如：

```text
90/100
```

不表示：

> “90% 会上涨。”

评分代表：

> **Research attractiveness under the defined framework.**

它用于：

```text
Prioritization
+
Comparison
+
Monitoring
```

而不是：

```text
Prediction
```

---

# 84. 最重要的 Ranking Logic

最终优先级遵循：

```text
Hard Veto
    >
Information Gap
    >
Primary Driver Strength
    >
Token Capture / Attention / Catalyst
    >
Liquidity
    >
Supply
    >
Reflexivity
```

解释：

首先必须有：

> **可能导致市场重新定价的信息差。**

然后才问：

> 信息差是通过什么机制实现？

然后才问：

> 市场是否有足够流动性交易这个故事？

最后才考虑：

> Reflexivity 能把它放大多少。

---

# 85. 最终决策树

每一个 Token 按以下顺序处理：

```text
                    TOKEN FOUND
                         │
                         ▼
                  Data Valid?
                   /        \
                 NO          YES
                 │            │
                 ▼            ▼
          Data Insufficient  Hard Veto?
                              /     \
                            YES      NO
                             │        │
                             ▼        ▼
                           Reject   Identify Archetype
                                      │
                                      ▼
                                Score 7 Dimensions
                                      │
                                      ▼
                               Evidence Adjustment
                                      │
                                      ▼
                                Regime Adjustment
                                      │
                                      ▼
                                Information Gap ≥3?
                                  /           \
                                NO             YES
                                │               │
                                ▼               ▼
                            Weak/Reject    Driver ≥4?
                                               /   \
                                             NO     YES
                                             │       │
                                             ▼       ▼
                                           Reject   Score Threshold
                                                        │
                                      ┌─────────────────┼─────────────────┐
                                      ▼                 ▼                 ▼
                                   ≥85              75–84             65–74
                                      │                 │                 │
                                  Deep DD          High Watch          Watch
```

---

# 86. Ultimate Research Rule

整个系统最终只需要问三个问题：

## Question 1

> **What is the market expecting?**

## Question 2

> **What could actually happen that is materially different?**

## Question 3

> **Does the Token capture that difference?**

然后再加：

```text
Can I enter?
Can I exit?
Can supply absorb the demand?
Is attention accelerating?
```

最终：

```text
Information Gap
×
Economic / Attention Driver
×
Token Capture
×
Liquidity
×
Supply
×
Reflexivity
```

才构成真正的：

> **Repricing Opportunity**

而不是：

```text
Cheap
+
Popular
+
Low MC
=
Opportunity
```