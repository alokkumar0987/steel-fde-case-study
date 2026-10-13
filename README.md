# Steel waste pilot: prototype

**Alok Kumar** · Forward Deployed Engineer case study (structural steel), prototype only

This public repository holds the **prototype** for my case study. The case study, the
one-page client note and the submission form were submitted through the hiring portal.
The client's discovery notes are confidential, so **no client material is here**: every
number in the prototype comes from synthetic data, except one check on the waste ranges
quoted in the task brief.

## The case in three lines

A structural steel fabricator asked for "AI for nesting". The real gap is **measurement**:
nobody can say how much steel is wasted, why, or what was preventable, and the optimiser
they want already exists in their software and has never been tested against hand nesting.
I recommend a 6-week pilot that measures first, tests the existing optimiser fairly and
blind, and lets management decide at week 6 against thresholds agreed in advance.

## What the prototype shows

Results with charts: **[prototype/output/results.md](prototype/output/results.md)**

| Pilot step | Result on synthetic data |
|---|---|
| Waste ledger with cause tagging | **PASS**: 90.5% of waste tagged with a cause; the unexplained 1.6 t equals exactly the parts missing from nest records, so the ledger finds record gaps instead of hiding them |
| Blind, paired, tonnage-weighted nesting benchmark | **STOP** on this data (−0.23 points). The stop rule works; the data was not tuned to say GO |
| Optimiser on default settings | Looks +0.22 points better on paper, but only **7%** of its nests can be cut (remnants too short for the saw to clamp). "Automatic wastes more" can be a settings problem |
| Stock length bought | Same cut lists: **2.6%** scrap from 12 m bars only, **0.6%** when the length is chosen per bar |
| Offcut matching (same project only) | **14%** of suggestions accepted; most rejections are offcuts too old to find in the yard |
| Plate vs profile split from the brief's ranges | Plate share can be anywhere from **0% to 33%** of tonnage; above 25%, plates waste more. A plate-only pilot could miss most of the money |

## Run it

```
cd prototype
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python run.py                     # writes prototype/output/results.md and 4 charts
python -m unittest discover -s tests     # 13 tests
```

Code layout, assumptions and limits: [prototype/README.md](prototype/README.md).
