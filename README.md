# Steel waste pilot: prototype

**Alok Kumar** · Forward Deployed Engineer case study (structural steel) · prototype only

This public repository holds the **prototype** for my case study. The case study, the
one-page client note and the submission form were submitted through the hiring portal.
The client's discovery notes are confidential, so **no client material is here**: every
number comes from synthetic data, except one check on the waste ranges quoted in the task brief.

---

## The case in three lines

A structural steel fabricator (~80,000 t a year) asked for "AI for nesting". The real gap
is **measurement**: nobody can say how much steel is wasted, why, or what was preventable,
and the optimiser they want already exists in their software, untested against hand
nesting. I recommend a **6-week pilot** that measures first, tests the existing optimiser
fairly and blind, and lets management decide at week 6 against thresholds agreed in advance.

This prototype runs that pilot's method end to end, so the plan is not only on paper.

---

## Architecture

```
                 ┌───────────────────────────────────────────────┐
                 │ config.py                                     │
                 │ every assumption, seed and pass/stop threshold│
                 └───────────────────────┬───────────────────────┘
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │ generate_data.py      synthetic ERP exports   │
                 │ 3 projects · 1,080 parts · 4 profile sections │
                 │ planted gaps: missing nest records, offcuts   │
                 │ lost in the yard, weighbridge noise on scrap  │
                 └───────────────────────┬───────────────────────┘
                                         ▼
     data/  stock_items · parts · nests · offcut_register · revisions · scrap_sales · new_parts
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                            ▼
┌───────────────────────┐  ┌───────────────────────────┐  ┌───────────────────────┐
│ ledger.py    (Test 1) │  │ benchmark.py     (Test 2) │  │ offcut_matcher.py     │
│ follow every bar      │  │ 30 nests × 3 methods:     │  │ next drawing release  │
│ through every cut     │  │  manual · auto default ·  │  │ same-project offcuts  │
│ tag each kg by cause  │  │  auto configured          │  │ smallest leftover     │
│ reconcile scrap sold  │  │ blind review file         │  │ simulated nester      │
│ → PASS / GAPS / STOP  │  │ → GO / STOP               │  │ → BUILD / STOP        │
│                       │  │ + stock-length study      │  │                       │
└───────────┬───────────┘  └─────────────┬─────────────┘  └───────────┬───────────┘
            │              ┌─────────────┴─────────────┐              │
            │              │ cutting.py   (shared)     │              │
            │              │ kerf · saw clamp rule ·   │              │
            │              │ first fit · FFD · best    │              │
            │              │ stock length per bar      │              │
            │              └───────────────────────────┘              │
            │                                                         │
            │              ┌───────────────────────────┐              │
            │              │ sensitivity.py            │              │
            │              │ plate/profile split from  │              │
            │              │ the brief's ranges (maths)│              │
            │              └─────────────┬─────────────┘              │
            └────────────────────────────┼────────────────────────────┘
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │ run.py    sanity checks (stop on failure):    │
                 │ ledger balances · blind file hides method ·   │
                 │ manual nests cuttable · maths = closed form   │
                 └───────────────────────┬───────────────────────┘
                                         ▼
                 charts.py ──► 4 PNG      report.py ──► output/results.md
```

### How the ledger accounts for every kilogram

A bar is followed through its whole **lineage**: its first cut, and every later cut of the
offcuts it produced. Every kilogram ends in exactly one bucket:

```
  bar bought (root_stock_id)
     │
     ├── cut 1 ──► parts ──┬── still valid ...................... good parts
     │                     └── superseded by a revision ......... revision waste (client / internal)
     │            kerf ........................................... nesting / process waste
     │            remnant < 1 m .................................. nesting / process waste
     │            remnant ≥ 1 m ──► offcut
     │                                 ├── reused ──► cut 2 ──► (same buckets again)
     │                                 ├── unused, ≤ 90 days ..... offcut in stock (not waste)
     │                                 └── unused, > 90 days ..... idle stock (reported apart)
     │
     └── bought − everything above .................................. unexplained (a finding in itself)
```

### How the benchmark stays fair

```
 30 past nests ──► rebuild the stock that existed that day (offcuts included)
                        │
          ┌─────────────┼──────────────────────────┐
          ▼             ▼                          ▼
       manual      auto, default settings      auto, configured (saw clamp length)
          └─────────────┼──────────────────────────┘
                        ▼
      blind_review.csv: random ids, no method column      (key kept apart in blind_key.csv)
                        ▼
      tonnage-weighted yield gain + share cuttable ──► thresholds fixed in config ──► GO / STOP
```

---

## Results

Full report with tables: **[prototype/output/results.md](prototype/output/results.md)**

| Pilot step | Verdict | Result on synthetic data |
|---|---|---|
| Waste ledger | **PASS** | 90.5% of waste tagged with a cause (pass ≥ 90%); scrap within 6% of scrap sold. The unexplained 1.6 t equals exactly the parts missing from nest records, so the ledger finds record gaps instead of hiding them |
| Nesting benchmark | **STOP** | Configured optimiser −0.23 points vs manual (pass ≥ +1). The data was not tuned to say GO; this shows the stop rule works |
| Default settings | **Finding** | +0.22 points on paper, but only **7%** of nests can be cut: the remnants are too short for the saw to clamp. "Automatic wastes more" can be a settings problem |
| Stock length | **Finding** | Same cut lists: **2.6%** scrap from 12 m bars only, **0.6%** when the length is chosen per bar |
| Offcut matching | **BUILD** | 14% of suggestions accepted (stop < 10%); most rejections are offcuts too old to find in the yard |
| Plate vs profile split | **Finding** | From the brief's ranges, plates can be **0% to 33%** of tonnage; above 25% they waste more than profiles |

### Waste by cause
![Waste by cause](prototype/output/waste_by_cause.png)

### Automatic minus manual yield, per nest
![Benchmark](prototype/output/benchmark_paired.png)

### Same cut lists, different stock lengths
![Stock length](prototype/output/stock_length_drop.png)

### Plate vs profile waste across the plate share
![Plate vs profile](prototype/output/plate_profile_range.png)

---

## Run it

```
cd prototype
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python run.py                     # rebuilds data, results.md and the 4 charts (deterministic, seed 42)
python -m unittest discover -s tests     # 13 tests
```

Change any assumption in `prototype/steelpilot/config.py` and the report rewrites its
findings from the new numbers.

## Limits, on purpose

- **Synthetic data.** It shows the method works, not what the client will save.
- **Profiles only (1D).** Plate nesting is 2D and the client's software already does it; the protocol is the same.
- **Stand-ins.** "Manual" is a replay (drawing order, first fit); in the pilot it is the real historical nest. The blind reviewer and the nester are rules; in the pilot they are people.

Code layout and module details: [prototype/README.md](prototype/README.md)
