"""Audit gate 5 (edit-mode write-back integrity).

Passworded edits to config/params.json must round-trip: write -> reload -> identical
engine result, with a change_log entry appended per edit, and an invalid edit must be
refused without touching the file. This proves edit mode can never silently corrupt the
source of truth.

The whole test runs on a TEMP COPY of the real config (never the real file):

  1. baseline engine result from the copy
  2. edit coat_material_price.value up -> reload -> result MUST change, change_log +1
  3. edit it back to original -> reload -> result IDENTICAL to baseline (round-trip), +2
  4. an out-of-range edit (value > slider max) MUST raise and leave the file unchanged

Exit 0 iff all hold (used by audit/run_gates.py).
"""

import shutil
import sys
import tempfile
from pathlib import Path

TEA = Path(__file__).resolve().parent
sys.path.insert(0, str(TEA / "engine"))
from params import load_config                       # noqa: E402
from model import default_params, run_model          # noqa: E402
from edit_mode import update_param                   # noqa: E402

REAL_CFG = TEA / "config" / "params.json"
KEY = "coat_material_price"
TOL = 1e-12


def cost(cfg):
    P = default_params(cfg)
    r = run_model(P, cfg)
    return r["full"]["total_m2"]


def main():
    problems = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "params.json"
        shutil.copy(REAL_CFG, tmp)

        cfg0 = load_config(tmp)
        base = cost(cfg0)
        orig = cfg0["params"][KEY]["value"]
        log0 = len(cfg0["params"][KEY]["change_log"])

        # 2. edit up
        update_param(KEY, "value", orig + 50, editor="gate5",
                     reason="round-trip test up", path=tmp)
        cfg1 = load_config(tmp)
        up = cost(cfg1)
        log1 = len(cfg1["params"][KEY]["change_log"])
        if not (up > base):
            problems.append(f"edit up did not raise cost ({base} -> {up})")
        if log1 != log0 + 1:
            problems.append(f"change_log not appended on edit up ({log0} -> {log1})")

        # 3. edit back -> identity
        update_param(KEY, "value", orig, editor="gate5",
                     reason="round-trip test back", path=tmp)
        cfg2 = load_config(tmp)
        back = cost(cfg2)
        log2 = len(cfg2["params"][KEY]["change_log"])
        if abs(back - base) > TOL * max(1.0, abs(base)):
            problems.append(f"round-trip not identical ({base} vs {back})")
        if log2 != log0 + 2:
            problems.append(f"change_log wrong after 2 edits ({log0} -> {log2})")

        # 4. invalid edit refused, file untouched
        before = tmp.read_text(encoding="utf-8")
        hi = cfg2["params"][KEY]["slider"]["max"]
        refused = False
        try:
            update_param(KEY, "value", hi + 1000, editor="gate5",
                         reason="should fail", path=tmp)
        except ValueError:
            refused = True
        if not refused:
            problems.append("out-of-range edit was NOT refused")
        if tmp.read_text(encoding="utf-8") != before:
            problems.append("refused edit still modified the file")

    print("=" * 60)
    print("AUDIT GATE 5 -- edit-mode write-back integrity")
    print("=" * 60)
    print(f"  baseline cost {base:.6f} $/m2")
    print(f"  edit up -> {up:.6f}; back -> {back:.6f} (round-trip)")
    print(f"  change_log: {log0} -> {log2} (+2 expected); invalid edit refused: {refused}")
    if problems:
        print(f"  PROBLEMS ({len(problems)}):")
        for pr in problems:
            print(f"    - {pr}")
    else:
        print("  PASS -- writes round-trip, log appends, invalid edits refused")
    return not problems


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
