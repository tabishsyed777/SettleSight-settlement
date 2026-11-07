# SettleSight

**A synthetic T+1 settlement-risk and liquidity control tower.**

SettleSight is a local-first prototype for exploring how settlement operations teams could
triage trades before their cutoff. It generates a synthetic trade book, fits an explainable
logistic-regression model, ranks potential settlement failures, recommends follow-up actions,
shows cash and collateral scenarios, and records why high-risk alerts were raised.

> This is a demonstration, not a production financial system. All trades, counterparties,
> balances, labels, and model results are synthetic. It is not connected to a bank, custodian,
> CSD, payment network, or market data feed.

## Live dashboard

The static dashboard is published on GitHub Pages:

**[Open SettleSight](https://tabishsyed777.github.io/SettleSight-settlement/)**

The page shows the generated scenario committed to the repository. It does not stream live
trades. To refresh the scenario, regenerate the files and push the updated outputs to main.

## Run locally

Requirements: Python 3.8 or newer. The generator uses only the Python standard library.

~~~bash
python3 src/build.py
~~~

Then open dist/index.html in a browser. On macOS:

~~~bash
open dist/index.html
~~~

You can also serve the dashboard locally:

~~~bash
python3 -m http.server 8000 --directory dist
~~~

Then visit http://localhost:8000.

The generator writes:

- dist/index.html — the self-contained dashboard with the current scenario embedded.
- data/synthetic_output.json — model metrics, scored trades, liquidity, collateral, and KPIs.
- data/audit_log.jsonl — one JSON alert record per high-risk trade.

The random seed is fixed in src/build.py, so rerunning the generator recreates the same
scenario.

## What the dashboard shows

| View | What it contains |
|---|---|
| Settlement runway | Simulated time remaining to cutoff, with markers for trades above low risk |
| Trade queue | Filterable and score-ranked book with counterparty, security, notional, risk score, and risk band |
| Trade detail | Model drivers, a suggested action, an illustrative avoided-cost estimate, and a schematic sese.023-style message fragment |
| Intraday liquidity | Expected cash and a stress case that removes at-risk receipts, compared with a minimum buffer |
| Collateral | Greedy cheapest-to-deliver allocation compared with a largest-assets-first baseline |
| Alert audit trail | Alert time, trade, model score, contributing drivers, suggested action, and status |

## How the prototype works

~~~mermaid
flowchart LR
  A[Synthetic historical trades] --> B[Feature standardisation]
  B --> C[Logistic regression]
  C --> D[Score simulated live book]
  D --> E[Explain risk drivers]
  E --> F[Recommend an operations action]
  D --> G[Liquidity stress and collateral allocation]
  F --> H[Static dashboard and audit log]
  G --> H
~~~

The current generator creates 6,000 synthetic historical records, 2,000 synthetic holdout
records, and 140 simulated trades for the dashboard. Fail labels are sampled from a formula
defined in the source. The model learns from those generated labels; this is a demonstration
of the pipeline, not evidence of real settlement-fail predictive performance.

The model is logistic regression trained by gradient descent. Features are standardised using
the historical training sample. The displayed feature contributions sum with the model bias
to produce the score, which makes each synthetic score inspectable.

## Sample scenario results

The committed scenario produced:

- Holdout AUC: 0.868; synthetic holdout fail rate: 5.9%.
- Dashboard book: 140 trades, including 8 high-risk and 18 medium-risk trades.
- High-risk notional: about $57.8 million.
- Expected fail cost: about $23,796; estimated saveable amount: about $9,463.
- Liquidity stress case: buffer breach at 18:00.
- Collateral cost: about $10,290 per day for the greedy allocation versus $15,278 for the baseline.

These figures are generated from made-up data and illustrative assumptions. They are useful
for exercising the user interface and pipeline only.

## Project structure

~~~text
.
├── src/
│   ├── build.py          # synthetic data, model, scoring, scenarios, audit, dashboard build
│   └── template.html     # dashboard template populated by the generator
├── dist/
│   └── index.html        # ready-to-open, self-contained dashboard
├── data/
│   ├── synthetic_output.json
│   └── audit_log.jsonl
├── docs/
│   ├── DATA_DICTIONARY.md
│   └── MODEL_CARD.md
└── .github/workflows/
    └── pages.yml         # publishes dist/ to GitHub Pages on pushes to main
~~~

## Data and model notes

- The risk thresholds, cost rates, counterparty fail rates, security liquidity, cash flows,
  and settlement outcomes are hand-authored or simulated.
- The recommended action is selected from the largest positive feature contribution.
- The saveable amount assumes a fixed 70% rescue rate. It is not measured performance.
- The ISO 20022 display is a schematic fragment for interface demonstration. It is not
  schema-validated and should not be sent to a market participant.
- The collateral allocator is greedy. It is not a linear or mixed-integer optimisation solver,
  and it does not model all real-world eligibility, concentration, or legal constraints.
- The liquidity stress case is a simple scenario, not a forecast.
- The audit file is a local JSONL example, not an immutable or access-controlled audit store.

Read [the model card](docs/MODEL_CARD.md) and [the data dictionary](docs/DATA_DICTIONARY.md)
for more detail.

## GitHub Pages deployment

The workflow at .github/workflows/pages.yml publishes the contents of dist/ after each push
to main. To refresh the hosted dashboard:

1. Run python3 src/build.py.
2. Commit the changed files in dist/ and data/.
3. Push the commit to main.
4. Check the Pages workflow under the repository's Actions tab.

The public dashboard URL is https://tabishsyed777.github.io/SettleSight-settlement/.

## Responsible use

Do not present the AUC or estimated savings as a validated result. A production pilot would
need real labelled data, chronological validation, calibration and drift analysis, model-risk
review, entitlements, secure message ingestion, operational controls, and human approval
before any action is taken. The illustrative $0.2m–$0.5m annual business-case estimate is a
separate back-of-the-envelope scenario, not a result produced by the model.

## Possible next improvements

1. Add proper chronological backtesting and calibration metrics.
2. Compare the baseline with gradient boosting and inspect explanations.
3. Replace the greedy collateral routine with a constrained optimiser.
4. Add a replay API and event stream using synthetic messages.
5. Add real screenshots of the dashboard after the walkthrough.
