# AGENTS.md

Working agreement for agents in this repository. Read this before starting.

## Project north star — persistent research goal

The user's active project-level goal is to keep searching for a genuinely
repeatable, cost-adjusted crypto market edge, then validate any survivor and
advance it only to an isolated Freqtrade dry-run. Read
[`docs-myself/RESEARCH_GOAL.md`](docs-myself/RESEARCH_GOAL.md) before substantive
research: it requires broad sourcing (papers, exchange documentation, GitHub,
forums and practitioner communities), recommends parallel subagents, and
specifies the preregistration, power, cost, OOS and safety gates.

**This is an objective, not a promise of profit or permission to p-hack.** The
project may explore new hypotheses, but every experiment must have a stop rule;
closed research lines stay closed unless new, independent evidence justifies a
pre-registered reopening. A dry-run is not proof of profitability. No real
orders, trade-enabled credentials or real funds without separate explicit user
authorization.

## 0. Maintain the research state file

**`docs-myself/RESEARCH_STATE.md` is the single source of truth for where this
project stands.** It carries the status of every research line, the traps that
have already been paid for, measured constants that must not be re-derived, and
the ordered next actions.

1. **Read it before starting substantive work.** It is cheaper than
   rediscovering a defect that was already found and fixed.
2. **Update it before finishing**, if your work changed any of: a research
   line's status, a measured constant, a known trap, a settled decision, or
   the next-action list. Add a change-log row. Keep it factual and terse.
3. When you correct something it previously got wrong, say so in the entry.
   Do not quietly overwrite a number.

The state file is append-and-correct, not a rewrite. Its value is that a later
agent can see what was believed, when, and what overturned it.

## 1. Look it up before you decide

**Do not start a substantive piece of work until you have checked whether the
approach is right.** Research first, then build.

Concretely, before committing to a non-obvious direction:

1. Search the literature and practitioner sources for the *specific* claim you
   are about to make — not the general topic.
2. Prefer primary sources. Peer-reviewed work, working papers, and exchange
   documentation beat blog posts. If the top results are SEO content or
   vendor marketing, that is itself a finding: note it, because it usually
   means the idea is heavily-mined and widely known, which is a reason for
   suspicion rather than enthusiasm.
3. Ask what the *canonical* established result is for the phenomenon, and at
   what horizon. If the documented effect lives at 1–12 months and you are
   proposing 4 hours, say so explicitly and treat the horizon mismatch as a
   reason for a lower prior, not a discovery.
4. Check whether the effect is documented enough to have been arbitraged away
   (McLean & Pontiff: the **total** post-publication decline in portfolio
   returns is **58%**; the 32% figure is only the data-mining component of it,
   i.e. 58% minus a 26% out-of-sample drop. The most arbitraged lose the most).
   No crypto analogue of that study exists, so the crypto decay rate is
   unmeasured — treat the equities figure as a prior, not a fact.
5. Write down the decision you are about to make and the evidence for and
   against it *before* you start. If the evidence is thin, say so.

Research is cheap relative to building the wrong thing, and a wrong direction
in a quantitative study can consume days and produce a convincing, worthless
result.

### 1a. Check that the experiment is capable of concluding

Before proposing a test, a forward period, or a data-collection effort, check
that the available data could produce a verdict at all. Compute the sample size
the measurement requires and compare it with what the design generates. A test
that cannot conclude is worse than no test: it consumes months and returns
"don't know" carrying false confidence.

This check killed the recommended next step in the Shark Hunter study. A
12-month forward test at the proposed universe would have produced roughly 5%
of the evidence needed, and after multiple-testing correction the required
sample size was *undefined* rather than merely large. The recommendation was
retracted rather than quietly carried out.

When the required sample size is undefined because the effect is smaller than
what pure luck already produces from the search performed, the correct
conclusion is to **stop that line of inquiry**, not to collect more of the same
data.

## 2. When the research contradicts you, say so

If the literature disagrees with what the work so far implies, the literature
wins and the earlier conclusion gets revised. Do not quietly keep building on a
premise that the research has undercut. If an earlier conclusion is found to be
wrong, state it plainly and correct the record rather than burying it.

## 3. Quantitative research discipline

These are the practices that have actually caught real bugs in this repo.
They are not aspirational; each one corresponds to a defect that was found and
fixed.

- **A regression gate runs before any result is believed.** For the Shark
  Hunter work that is `python -m shark_hunter.tests.test_regressions`. For the
  research framework it is `pytest tests/tools/` (see §4 for the exact
  invocation and the plugins it needs). A hand-written runner that skips
  fixture-bearing tests is **not** a regression gate — it silently under-reports
  and looks green.
- **A silent dead signal must fail the build, not look like a weak result.**
  A boolean mask built with `&=` starting from an all-`False` array stays
  all-`False` forever, producing exactly zero entries — indistinguishable from
  "no edge". Every strategy must be asserted to produce a non-zero number of
  signals on data where its feeds are present.
- **A missing data feed is `BLOCKED`, not `FAILED`.** Never let a strategy
  dependent on an unavailable feed run silently on all-NaN columns. Never
  substitute a proxy for a feed the user believes you have and report the
  result as if it answered the original question.
- **Assert causality by truncation, not by inspection.** Recompute every
  feature on a truncated history and assert the shared bars are bit-identical.
  That catches lookahead that hand-written rule checks miss.
- **Report in units of risk (R), not cash.** A losing strategy drives cash
  equity to zero, after which every cash-based ratio describes a dead account
  rather than the strategy.
- **Publish the curve, never the chosen cell.** Report parameter sensitivity
  as a frontier. Selecting the best setting after seeing results is the
  multiple-testing error the whole exercise exists to avoid, and the DSR /
  multiple-testing correction should be deflated for the widened search
  whenever the search is widened.
- **State the trap when the experiment design contains one.** If a timeframe or
  parameter was chosen after earlier ones failed, say so in the report. A
  result selected that way must not be presented as a clean finding.
- **Fix over-strict data checks before loosening them.** An integrity rule
  that rejects legitimate data (e.g. flagging `high == low` as a corrupt bar)
  will make real problems look like data errors.

## 4. Environment notes for this repository

- Python 3.11, pandas 3.0, numpy 2.4, **pyarrow 25.0.1 is installed** (an
  earlier version of this file said otherwise — the ~225 feather files load
  directly). No matplotlib or statsmodels.
- **pytest IS installed** (9.1.1) together with `pytest-xdist` and
  `pytest-mock`. An earlier version of this file said otherwise, and the
  consequence was that the suite was never run properly: the reported test
  counts came from a hand-written runner that silently skipped every
  fixture-bearing test. `tests/conftest.py` requires both `mocker` (from
  `pytest-mock`) and `xdist`, so installing bare `pytest` is not enough.
  Run the suite with:
  ```
  .venv\Scripts\python.exe -m pytest tests/tools/ -q --no-header -p no:cacheprovider
  ```
  A result from a custom runner is not a result from the test suite.
- PowerShell `Invoke-WebRequest` fails TLS against some data hosts; Python
  `requests` works. Use Python for network access.
- pandas 3.0 gotchas that have bitten here: `pd.to_datetime` on a *named* Index
  needs an explicit int64 array; `parse_dates=True` does not reliably parse a
  CSV *index* column; subtracting two differently-indexed Series aligns on
  index and silently yields NaN (use `.to_numpy()`).
- There are no charts and no plotting library. If a chart is genuinely needed,
  hand-roll SVG rather than adding a dependency.

## 5. Communication

- The user reads conclusions, not method. Lead with what was found and whether
  it is actionable; keep the technical detail in the report and in the reply
  underneath it.
- A negative result is a valid result. Report it plainly; do not soften a null
  finding into a "promising" one to make the work feel worthwhile.
- When a result is only partly positive, say which part survived and which did
  not, in those words.
