# Steel Waste Pilot: prototype

A small, runnable version of the pilot in the case study, on **synthetic data**. It
shows that the method works end to end: the waste ledger, the manual vs automatic
nesting benchmark, the stock-length study and offcut matching. It does **not** show
how much the client will save. Only the plate/profile check (section 5 of the
results) uses the client's own figures.

Results: [`output/results.md`](output/results.md)

## What it shows

| Case study claim | Section | How the prototype checks it |
|---|---|---|
| A waste ledger with cause tagging can be built from ERP-like exports | 4.3, 5.1 Test 1 | Traces every bar through every cut (offcuts included), tags each kg, reconciles scrap with sales, and finds the planted missing records |
| The benchmark protocol runs (paired, tonnage-weighted, blind, thresholds set first) | 5.1 Test 2, 5.2 | 30 nests re-run with the stock of the day, written to a blind review file, GO/STOP from `config.THRESHOLDS` |
| "Automatic wastes more" may be a settings problem | 2, 3.1 A | Automatic nesting with default settings vs configured with the saw's clamp length |
| Profile waste depends on the stock length bought | 3.1 G | Same cut lists from 6 / 9 / 12 m stock and from the best length per bar |
| Simple offcut matching works, and its stop rule can be measured | 4.3, 5.2 | Same-project suggestions, simulated accept/reject with reasons, cross-project matches counted as blocked |
| The plate/profile split is uncertain within the client's ranges | 1.2 | Closed-form plate share and crossover from the stated ranges |

## Setup

Python 3.11+.

```
cd prototype
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

## Run

```
python run.py                            # data -> ledger -> benchmark -> charts -> output/results.md
python -m unittest discover -s tests     # 13 tests
```

`run.py` stops with an error if the ledger does not balance, the blind file leaks the
method, manual nests are uncuttable, or the sensitivity maths differs from its closed form.

## Layout

```
prototype/
├── run.py                  one command for the whole pipeline
├── requirements.txt        numpy, pandas, matplotlib (pinned)
├── steelpilot/
│   ├── config.py           every assumption and threshold, in one place
│   ├── cutting.py          1D bar cutting: kerf, clamp rule, manual / automatic / best-length
│   ├── generate_data.py    synthetic ERP-like exports, with planted imperfections
│   ├── ledger.py           waste ledger and cause tagging (Test 1)
│   ├── benchmark.py        manual vs automatic benchmark (Test 2) and stock-length study
│   ├── offcut_matcher.py   offcut suggestions for the next drawing release
│   ├── sensitivity.py      plate/profile split from the client's ranges
│   ├── charts.py           four PNG charts
│   └── report.py           output/results.md
├── tests/test_prototype.py
├── data/                   generated CSVs (stock, parts, nests, offcuts, revisions, scrap sales)
└── output/                 results.md, charts, ledger, benchmark and blind-review files
```

## Limits (on purpose)

- **Synthetic data.** Waste rates, verdicts and savings here are not the client's.
  Change `steelpilot/config.py` and the report rewrites its findings from the new numbers.
- **Profiles only (1D).** Plate nesting is 2D and the client's software already does it; the protocol is the same.
- **Stand-ins.** "Manual" is a replay (drawing order, first fit); in the pilot it is the real
  historical nest. The blind reviewer and the nester are rules; in the pilot they are people.
- **No client data.** The client's discovery notes, the case study and the client note are confidential and are not in this repository. The "Section" column above refers to the case study, which was submitted separately.
