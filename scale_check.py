"""Scale-invariance check (the intensive-first proof).

Changing throughput (web speed / width) must leave the per-m2 VARIABLE economics
(coating, substrate, throughput energy, disposal) exactly invariant, while:
  - extensive throughput (annual good m2) scales by the area-rate ratio, and
  - the per-m2 FIXED stack (labor, overhead, baseline energy) DILUTES (falls) as it
    spreads over more m2.

That split -- a fixed per-m2 floor that moves and a variable floor that doesn't -- is
exactly what the dashboard's production-scale reframe leans on. Exit 0 iff it holds.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_params          # noqa: E402
from mass_balance import mass_balance     # noqa: E402
from tea import tea                       # noqa: E402


def scenario(P):
    mb = mass_balance(P)
    t = tea(P, mb)
    mat, conv, geo = t["materials"], t["conversion"], mb["geo"]
    return {
        # variable (must be invariant)
        "coating_m2": mat["coating_mat_m2"],
        "substrate_m2": mat["substrate_m2"],
        "materials_m2": mat["materials_produced_m2"],
        "energy_var_m2": conv["energy_var_m2"],
        "disposal_m2": conv["disposal_m2"],
        # fixed (must dilute as throughput rises)
        "labor_m2": conv["labor_m2"],
        "overhead_m2": conv["overhead_m2"],
        "energy_fixed_m2": conv["energy_fixed_m2"],
        # extensive (must scale)
        "area_rate": geo["area_rate_m2ph"],
        "annual_m2": conv["annual_m2"],
    }


def main():
    base = load_params()
    scaled = dict(base)
    scaled["web_speed"] = base["web_speed"] * 1.75
    scaled["web_width"] = base["web_width"] * 1.50
    rate_ratio = 1.75 * 1.50

    b = scenario(base)
    s = scenario(scaled)

    variable = ["coating_m2", "substrate_m2", "materials_m2", "energy_var_m2", "disposal_m2"]
    fixed = ["labor_m2", "overhead_m2", "energy_fixed_m2"]

    print("=" * 72)
    print(f"Scale invariance: base vs {rate_ratio:.2f}x throughput")
    print("=" * 72)
    print(f"  {'item':<18} {'base $/m2':>12} {'scaled $/m2':>13}  class")
    problems = []

    for k in variable:
        rel = abs(b[k] - s[k]) / abs(b[k]) if b[k] else abs(s[k])
        ok = rel <= 1e-9
        if not ok:
            problems.append(f"VARIABLE {k} not invariant (rel {rel:.2e})")
        print(f"  {k:<18} {b[k]:>12.5f} {s[k]:>13.5f}  variable {'OK' if ok else 'FAIL'}")

    for k in fixed:
        ok = s[k] < b[k] - 1e-12 or (b[k] == 0 and s[k] == 0)
        if not ok:
            problems.append(f"FIXED {k} did not dilute ({b[k]:.5f} -> {s[k]:.5f})")
        print(f"  {k:<18} {b[k]:>12.5f} {s[k]:>13.5f}  fixed {'OK (diluted)' if ok else 'FAIL'}")

    # extensive: annual good m2 scales by the area-rate ratio
    got_ratio = s["annual_m2"] / b["annual_m2"]
    ext_ok = abs(got_ratio - rate_ratio) <= 1e-9 * rate_ratio
    if not ext_ok:
        problems.append(f"annual m2 scaled by {got_ratio:.4f}, expected {rate_ratio:.4f}")
    print(f"\n  annual good m2: {b['annual_m2']:,.0f} -> {s['annual_m2']:,.0f} "
          f"({got_ratio:.3f}x, expected {rate_ratio:.3f}x)  {'OK' if ext_ok else 'FAIL'}")

    print("\n" + "-" * 72)
    if problems:
        print(f"SCALE INVARIANCE: FAIL ({len(problems)})")
        for pr in problems:
            print(f"  - {pr}")
    else:
        print("SCALE INVARIANCE: PASS -- variable floor invariant, fixed dilutes, throughput scales")
    return not problems


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
