"""Mass-balance row-level check (Demo Co. membrane).

Companion to the closed-balance gate (streams.py) and the regression gate
(engine/run.py). Checks each mass-balance intermediate at the pilot defaults against
its expected value (exact arithmetic -- coated solids have no discretization). Exit 0
iff all rows pass (used by audit/run_gates.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_params          # noqa: E402
from mass_balance import mass_balance    # noqa: E402


def main():
    P = load_params()
    mb = mass_balance(P)
    geo, coat, waste = mb["geo"], mb["coat"], mb["waste"]

    # (label, computed, expected, abs_tolerance) -- all machine-exact
    checks = [
        ("Roll area (m2)", geo["area_m2"], 600.0, 1e-9),
        ("Area rate (m2/h)", geo["area_rate_m2ph"], 24.0, 1e-9),
        ("Proc time per roll (h)", geo["proc_time_h"], 25.0, 1e-9),
        ("Coating loading (kg/m2)", coat["coat_kg_per_m2"], 0.025, 1e-12),
        ("Substrate areal (kg/m2)", coat["substrate_kg_per_m2"], 0.090, 1e-12),
        ("Total solids (kg/m2)", coat["total_kg_per_m2"], 0.115, 1e-12),
        ("Coating (kg/roll)", coat["coat_kg_per_roll"], 15.0, 1e-9),
        ("Substrate (kg/roll)", coat["substrate_kg_per_roll"], 54.0, 1e-9),
        ("Total solids (kg/roll)", coat["total_kg_per_roll"], 69.0, 1e-9),
        ("Scrap fraction", waste["scrap_frac"], 0.10, 1e-12),
        ("Waste solids (kg/roll)", waste["waste_kg_per_roll"], 6.9, 1e-9),
        ("Product solids (kg/roll)", waste["product_kg_per_roll"], 62.1, 1e-9),
    ]

    width = max(len(r[0]) for r in checks)
    n_pass = 0
    print(f"{'metric':<{width}}  {'computed':>16}  {'expected':>16}  result")
    print("-" * (width + 44))
    for label, got, want, tol in checks:
        ok = got is not None and abs(got - want) <= tol
        n_pass += ok
        gs = "None" if got is None else f"{got:.8g}"
        print(f"{label:<{width}}  {gs:>16}  {want:>16.8g}  {'PASS' if ok else 'FAIL'}")
    print("-" * (width + 44))
    print(f"{n_pass}/{len(checks)} passed")
    return n_pass == len(checks)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
