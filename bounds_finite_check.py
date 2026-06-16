"""Audit gate 12 -- no reachable slider extreme is a singularity.

The dashboard lets viewers drag any lever to its slider min/max, and lets editors RE-SET those
bounds. A bound sitting on a model singularity (a denominator -> 0; e.g. oee_quality=0 zeroing
good-output m2, the whole cost stack's denominator) crashes the live app or shows inf/nan. This
gate sweeps every lever to BOTH bounds (others at the deliverable opening default), runs the
engine, and requires a finite headline with no exception.

Paired with the per-param `hard_min` floors (which keep the editable bounds off the
singularities, enforced by edit_mode.bounds + the provenance gate), this guarantees no
draggable/edited extreme can blow up the deliverable. Exit 0 iff every bound is finite.
"""

import math
import sys
from pathlib import Path

TEA = Path(__file__).resolve().parent
sys.path.insert(0, str(TEA / "engine"))
from params import load_config                       # noqa: E402
from model import default_params, run_model          # noqa: E402

HEADLINE = ("cost_per_m2", "revenue_per_m2", "margin_per_m2", "annual_gross_profit")


def _levers(cfg):
    hidden = set(cfg["_meta"].get("hidden_factors", {}).get("keys", []))
    return [k for k, m in cfg["params"].items()
            if m.get("status") != "constant" and m.get("tier") not in ("fixed", "negligible")
            and isinstance(m.get("slider"), dict) and k not in hidden]


def _bad_at(cfg, key, val):
    P = default_params(cfg)
    P[key] = val
    try:
        r = run_model(P, cfg)
    except Exception as e:                            # noqa: BLE001 - a crash IS the failure
        return f"engine raised {type(e).__name__}"
    vals = {"cost_per_m2": r["full"]["total_m2"],
            "revenue_per_m2": r["value"]["revenue_per_m2"],
            "margin_per_m2": r["value"]["margin_per_m2"],
            "annual_gross_profit": r["value"]["annual_gross_profit"]}
    bad = [f"{n}={v}" for n, v in vals.items() if v is None or not math.isfinite(v)]
    return ("non-finite " + ", ".join(bad)) if bad else None


def main():
    cfg = load_config()
    levers = _levers(cfg)
    problems = []
    for k in levers:
        sl = cfg["params"][k]["slider"]
        for bound in ("min", "max"):
            msg = _bad_at(cfg, k, sl[bound])
            if msg:
                problems.append(f"{k} at {bound}={sl[bound]}: {msg}")

    print("=" * 60)
    print("AUDIT GATE 12 -- no slider extreme is a singularity")
    print("=" * 60)
    print(f"  levers swept: {len(levers)} x2 bounds")
    if problems:
        print(f"  PROBLEMS ({len(problems)}):")
        for pr in problems:
            print(f"    - {pr}")
    else:
        print("  PASS -- every lever min/max yields a finite headline")
    return not problems


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
