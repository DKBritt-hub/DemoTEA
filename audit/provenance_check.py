"""Audit gate 2 -- parameter provenance & slider integrity.

Operationalizes the gap-awareness discipline at the data layer: no client-facing
number may flow from a param that is not status-tagged with a source, every estimate
or TBD value must carry a stated rationale (the "how we got it" the modeling
philosophy requires), and every user-facing lever must expose a slider whose range
actually contains its current value. Client-provided values take the client as their
provenance (the source field) and do not each need a sentence of rationale.

Exit 0 iff clean (used by audit/run_gates.py).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
from edit_mode import bounds   # noqa: E402  -- share the exact editor bound rules

CFG = Path(__file__).resolve().parent.parent / "config" / "params.json"
REQUIRED = ["label", "value", "unit", "status", "category", "tier", "slider",
            "source", "change_log"]
# statuses where WE supply the number and therefore owe explicit logic
NEEDS_RATIONALE = {"estimate", "TBD"}


def main():
    cfg = json.loads(CFG.read_text())
    meta = cfg["_meta"]
    status_vocab = set(meta["status_vocab"])
    tier_vocab = set(meta["tier_vocab"])
    params = cfg["params"]
    problems = []

    for k, p in params.items():
        for key in REQUIRED:
            if key not in p:
                problems.append(f"{k}: missing required field '{key}'")
        if p.get("status") not in status_vocab:
            problems.append(f"{k}: status '{p.get('status')}' not in status_vocab")
        if p.get("tier") not in tier_vocab:
            problems.append(f"{k}: tier '{p.get('tier')}' not in tier_vocab")
        if not (p.get("source") or "").strip():
            problems.append(f"{k}: empty source (provenance required)")
        if p.get("status") in NEEDS_RATIONALE and not (p.get("notes") or "").strip():
            problems.append(f"{k}: status '{p['status']}' requires a rationale in notes")

        # slider integrity for user levers (constants / fixed-tier are exempt)
        is_lever = p.get("status") != "constant" and p.get("tier") != "fixed"
        sl = p.get("slider")
        if is_lever:
            if not isinstance(sl, dict):
                problems.append(f"{k}: lever has no slider range")
            else:
                lo, hi, st, v = sl.get("min"), sl.get("max"), sl.get("step"), p.get("value")
                if lo is None or hi is None or st is None:
                    problems.append(f"{k}: slider missing min/max/step")
                else:
                    if not lo < hi:
                        problems.append(f"{k}: slider min {lo} not < max {hi}")
                    if st <= 0:
                        problems.append(f"{k}: slider step {st} not > 0")
                    elif st > hi - lo:
                        problems.append(f"{k}: slider step {st:g} exceeds range {hi - lo:g}")
                    hard_min, hard_max = bounds(p)
                    if lo < hard_min:
                        problems.append(f"{k}: slider min {lo:g} below floor {hard_min:g}")
                    if hi > hard_max:
                        problems.append(f"{k}: slider max {hi:g} above ceiling {hard_max:g}")
                    if v is None or not lo <= v <= hi:
                        problems.append(f"{k}: value {v} outside slider [{lo}, {hi}]")

    print("=" * 60)
    print("AUDIT GATE 2 -- param provenance & slider integrity")
    print("=" * 60)
    print(f"  params checked: {len(params)}")
    if problems:
        print(f"  PROBLEMS ({len(problems)}):")
        for pr in problems:
            print(f"    - {pr}")
    else:
        print("  PASS -- every param tagged, sourced; estimates justified; "
              "lever sliders valid")
    return not problems


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
