"""Generate synthetic, ERP-like exports (fabrication / nesting software) for three projects.

Files written to data/:
  stock_items.csv      bars bought (one row per new stock bar)
  parts.csv            every part, its drawing, length, weight, nest and status
  nests.csv            one row per cut event: which bar was cut, which parts, what remained
  offcut_register.csv  offcuts created, when, and whether they were used again
  revisions.csv        parts superseded after cutting, with the reason
  scrap_sales.csv      scrap sold per project (weighbridge figure, with noise)
  new_parts.csv        next drawing release, waiting to be nested (for the offcut matcher)

Deliberate imperfections, so the ledger has something to find:
  - some nest records miss one part line (-> "unexplained" waste)
  - some offcuts are never seen again by nesters (-> idle stock)
  - scrap sold differs from the ledger by weighbridge noise
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from . import config as C
from .cutting import manual_nest


def _kg(section: str, length_mm: int) -> float:
    return round(C.SECTIONS[section] * length_mm / 1000, 2)


def _make_parts(rng, project: str, n: int, prefix: str = "") -> pd.DataFrame:
    sections = rng.choice(list(C.SECTIONS), size=n)
    lengths = (rng.integers(C.PART_LENGTH_MM[0], C.PART_LENGTH_MM[1], size=n) // 10) * 10
    rows = []
    for i, (sec, length) in enumerate(zip(sections, lengths), start=1):
        rows.append({
            "part_id": f"{project}-{prefix}{i:04d}",
            "project": project,
            "section": sec,
            "drawing": f"D-{project}-{prefix}{(i - 1) // 6 + 1:03d}",  # ~6 parts per drawing
            "rev": 0,
            "length_mm": int(length),
            "weight_kg": _kg(sec, int(length)),
        })
    return pd.DataFrame(rows)


def generate(seed: int = C.SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    start = C.TODAY - timedelta(days=360)

    parts = pd.concat([_make_parts(rng, p, C.PARTS_PER_PROJECT) for p in C.PROJECTS], ignore_index=True)
    parts["nest_id"] = ""
    parts["status"] = "cut"

    stock_rows, nest_rows, offcut_rows = [], [], []
    stock_seq = offcut_seq = nest_seq = 0
    # offcuts nesters can see, per (project, section): list of dicts (mutable state)
    visible: dict[tuple[str, str], list[dict]] = {}

    # Build nests: per project and section, chunk parts in drawing order, spread over the year
    groups = []
    for (project, section), g in parts.groupby(["project", "section"], sort=True):
        ids = g.index.tolist()
        i = 0
        while i < len(ids):
            size = int(rng.integers(C.NEST_SIZE[0], C.NEST_SIZE[1] + 1))
            groups.append((project, section, ids[i:i + size]))
            i += size
    order = rng.permutation(len(groups))
    days = np.sort(rng.integers(0, 330, size=len(groups)))

    for slot, gi in enumerate(order):
        project, section, idx = groups[gi]
        nest_seq += 1
        nest_id = f"N{nest_seq:04d}"
        nest_date = start + timedelta(days=int(days[slot]))
        parts.loc[idx, "nest_id"] = nest_id

        pool = visible.setdefault((project, section), [])
        offcuts = [(o["offcut_id"], o["length_mm"]) for o in pool]
        part_list = list(zip(parts.loc[idx, "part_id"], parts.loc[idx, "length_mm"]))
        bars = manual_nest(part_list, offcuts)

        for bar in bars:
            if bar.is_offcut:
                src = next(o for o in pool if o["offcut_id"] == bar.source_id)
                pool.remove(src)
                rec = next(r for r in offcut_rows if r["offcut_id"] == bar.source_id)
                rec["used_date"] = nest_date.isoformat()
                root = src["root_stock_id"]
            else:
                stock_seq += 1
                bar.source_id = f"S{stock_seq:05d}"
                root = bar.source_id
                stock_rows.append({
                    "stock_id": bar.source_id, "project": project, "section": section,
                    "length_mm": bar.length_mm, "weight_kg": _kg(section, bar.length_mm),
                    "purchase_date": (nest_date - timedelta(days=int(rng.integers(5, 40)))).isoformat(),
                })

            remnant = bar.remnant_mm
            offcut_id = ""
            if remnant >= C.MIN_USABLE_OFFCUT_MM:
                offcut_seq += 1
                offcut_id = f"O{offcut_seq:05d}"
                rec = {"offcut_id": offcut_id, "root_stock_id": root, "project": project,
                       "section": section, "length_mm": remnant, "weight_kg": _kg(section, remnant),
                       "created_date": nest_date.isoformat(), "used_date": ""}
                offcut_rows.append(rec)
                # Some offcuts are put away and never seen by nesters again
                if rng.random() >= C.OFFCUT_UNUSED_RATE:
                    pool.append({**rec})

            nest_rows.append({
                "nest_id": nest_id, "nest_date": nest_date.isoformat(), "project": project,
                "section": section, "source_id": bar.source_id, "root_stock_id": root,
                "source_is_offcut": bar.is_offcut, "source_length_mm": bar.length_mm,
                "part_ids": ";".join(pid for pid, _ in bar.cuts), "n_cuts": len(bar.cuts),
                "remnant_mm": remnant,
                "remnant_type": "offcut" if offcut_id else ("scrap" if remnant > 0 else "none"),
                "offcut_id": offcut_id,
            })

    stock = pd.DataFrame(stock_rows)
    nests = pd.DataFrame(nest_rows)
    offcuts = pd.DataFrame(offcut_rows)
    offcuts["age_days"] = offcuts["created_date"].map(lambda d: (C.TODAY - pd.Timestamp(d).date()).days)

    # Revisions: some cut parts were superseded after cutting
    cut_idx = parts.index[parts["nest_id"] != ""]
    sup = rng.choice(cut_idx, size=int(len(cut_idx) * C.REVISION_RATE), replace=False)
    parts.loc[sup, "status"] = "superseded"
    revisions = parts.loc[sup, ["part_id", "project", "drawing"]].copy()
    revisions["new_rev"] = 1
    revisions["reason"] = np.where(rng.random(len(sup)) < C.CLIENT_REVISION_SHARE, "client", "internal")
    revisions = revisions.sort_values("part_id").reset_index(drop=True)

    # Missing records: a few nest rows lose one part line; that part also loses its nest link
    multi = nests.index[nests["n_cuts"] >= 2]
    broken = rng.choice(multi, size=int(len(nests) * C.MISSING_RECORD_RATE), replace=False)
    superseded = set(parts.loc[sup, "part_id"])
    for i in broken:
        ids = nests.at[i, "part_ids"].split(";")
        candidates = [p for p in ids if p not in superseded]
        if not candidates:
            continue
        dropped = candidates[int(rng.integers(len(candidates)))]
        ids.remove(dropped)
        nests.at[i, "part_ids"] = ";".join(ids)
        parts.loc[parts["part_id"] == dropped, "nest_id"] = ""

    # Scrap sold: true physical scrap (short remnants + superseded parts), with weighbridge noise
    kg_per_mm = nests["section"].map(C.SECTIONS) / 1000
    nests_scrap = nests.assign(scrap_kg=np.where(nests["remnant_type"] == "scrap", nests["remnant_mm"] * kg_per_mm, 0))
    true_scrap = nests_scrap.groupby("project")["scrap_kg"].sum() + \
        parts[parts["status"] == "superseded"].groupby("project")["weight_kg"].sum()
    noise = 1 + rng.uniform(-C.SCRAP_SALES_NOISE, C.SCRAP_SALES_NOISE, len(true_scrap))
    scrap_sales = pd.DataFrame({"project": true_scrap.index,
                                "scrap_sold_kg": (true_scrap.values * noise).round(0)})

    # Next drawing release per project, waiting to be nested
    new_parts = pd.concat([_make_parts(rng, p, 40, prefix="R") for p in C.PROJECTS], ignore_index=True)

    return {"stock_items": stock, "parts": parts, "nests": nests, "offcut_register": offcuts,
            "revisions": revisions, "scrap_sales": scrap_sales, "new_parts": new_parts}


def write(tables: dict[str, pd.DataFrame]) -> None:
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(C.DATA_DIR / f"{name}.csv", index=False)


def load() -> dict[str, pd.DataFrame]:
    names = ["stock_items", "parts", "nests", "offcut_register", "revisions", "scrap_sales", "new_parts"]
    tables = {n: pd.read_csv(C.DATA_DIR / f"{n}.csv", keep_default_na=False) for n in names}
    tables["nests"]["part_ids"] = tables["nests"]["part_ids"].astype(str)
    return tables
