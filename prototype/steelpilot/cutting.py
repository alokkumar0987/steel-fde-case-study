"""1D cutting of profile bars: shared by the data generator, benchmark and stock-length study.

A "bar" is either a new stock length or an existing offcut. Each cut consumes the
part length plus one kerf. What is left on the bar at the end is the remnant:
an offcut if it is long enough to reuse, otherwise scrap.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C


@dataclass
class Bar:
    source_id: str          # stock item id or offcut id ("" for a bar not yet bought)
    length_mm: int
    is_offcut: bool = False
    cuts: list[tuple[str, int]] = field(default_factory=list)  # (part_id, length_mm)

    @property
    def used_mm(self) -> int:
        return sum(length for _, length in self.cuts) + C.KERF_MM * len(self.cuts)

    @property
    def remnant_mm(self) -> int:
        return self.length_mm - self.used_mm

    def fits(self, length_mm: int, respect_clamp: bool = False) -> bool:
        after = self.remnant_mm - (length_mm + C.KERF_MM)
        if after < 0:
            return False
        # The saw must clamp the last piece: a remnant between 0 and CLAMP_MM cannot be cut
        return not respect_clamp or after == 0 or after >= C.CLAMP_MM

    def add(self, part_id: str, length_mm: int) -> None:
        if not self.fits(length_mm):
            raise ValueError(f"part {part_id} ({length_mm} mm) does not fit bar {self.source_id}")
        self.cuts.append((part_id, length_mm))


def first_fit(parts: list[tuple[str, int]], offcuts: list[tuple[str, int]],
              new_length_mm: int = C.STOCK_LENGTH_MM, respect_clamp: bool = False) -> list[Bar]:
    """Place parts in the order given. Offcuts are tried first (nesters check them
    first), then bars already opened, then a new bar is opened. Returns used bars only."""
    bars = [Bar(oid, length, is_offcut=True) for oid, length in offcuts]
    for part_id, length in parts:
        target = next((b for b in bars if b.fits(length, respect_clamp)), None)
        if target is None:
            target = Bar("", new_length_mm)
            bars.append(target)
        target.add(part_id, length)
    return [b for b in bars if b.cuts]


def manual_nest(parts, offcuts, new_length_mm=C.STOCK_LENGTH_MM):
    """Stand-in for hand nesting: parts in drawing order, first fit. A nester knows the
    saw, so never leaves a remnant too short to clamp."""
    return first_fit(parts, offcuts, new_length_mm, respect_clamp=True)


def auto_nest(parts, offcuts, new_length_mm=C.STOCK_LENGTH_MM, configured: bool = True):
    """Stand-in for an automatic optimiser: First-Fit Decreasing (longest parts first).
    configured=False mimics default settings with no minimum-clamp rule set."""
    return first_fit(sorted(parts, key=lambda p: -p[1]), offcuts, new_length_mm, respect_clamp=configured)


def best_length_nest(parts: list[tuple[str, int]], lengths=C.STOCK_LENGTH_OPTIONS_MM) -> list[Bar]:
    """Stock-length planning: each time a new bar is needed, buy the standard length
    that leaves the smallest remnant when filled with the remaining parts (FFD)."""
    remaining = sorted(parts, key=lambda p: -p[1])
    bars: list[Bar] = []
    while remaining:
        best = None
        for length in lengths:
            trial = Bar("", length)
            for pid, plen in remaining:
                if trial.fits(plen):
                    trial.add(pid, plen)
            if trial.cuts and (best is None or trial.remnant_mm / length < best.remnant_mm / best.length_mm):
                best = trial
        bars.append(best)
        placed = {pid for pid, _ in best.cuts}
        remaining = [p for p in remaining if p[0] not in placed]
    return bars


def summarise(bars: list[Bar]) -> dict:
    """Yield and loss figures for a set of cut bars (all lengths in mm).

    Yield = part length / (stock consumed - usable offcuts returned). Usable offcuts
    go back to stock, so they are not waste; this matches the ledger definition.
    """
    parts = sum(length for b in bars for _, length in b.cuts)
    consumed = sum(b.length_mm for b in bars)
    kerf = sum(C.KERF_MM * len(b.cuts) for b in bars)
    offcut_back = sum(b.remnant_mm for b in bars if b.remnant_mm >= C.MIN_USABLE_OFFCUT_MM)
    scrap = sum(b.remnant_mm for b in bars if b.remnant_mm < C.MIN_USABLE_OFFCUT_MM)
    net = consumed - offcut_back
    return {
        "parts_mm": parts,
        "consumed_mm": consumed,
        "kerf_mm": kerf,
        "offcut_mm": offcut_back,
        "scrap_mm": scrap,
        "new_bars": sum(1 for b in bars if not b.is_offcut),
        "offcuts_used": sum(1 for b in bars if b.is_offcut),
        "yield": parts / net if net else 0.0,
        "cuttable": all(not (0 < b.remnant_mm < C.CLAMP_MM) for b in bars),
    }
