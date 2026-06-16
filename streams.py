"""Closed mass balance (Demo Co. membrane): where does every kg of solids go?

The coated web is a closed solids balance:

  INPUTS (per roll)            OUTPUTS (per roll)
    coating formulation   -->    PRODUCT solids   (good area, = yield x in)
    support substrate     -->    SCRAP solids     ((1 - yield) x in -> disposal)

  solids in == product + scrap   (no accumulation)

Verified at the pilot defaults AND at a perturbed throughput (different speed/width), to
show closure holds regardless of scale. Exit 0 iff it closes (used by audit/run_gates.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_params          # noqa: E402
from mass_balance import mass_balance     # noqa: E402

TOL = 1e-12


def closure(P):
    mb = mass_balance(P)
    coat, waste, geo = mb["coat"], mb["waste"], mb["geo"]
    solids_in = coat["total_kg_per_roll"]
    out = waste["product_kg_per_roll"] + waste["waste_kg_per_roll"]
    return {
        "area_m2": geo["area_m2"],
        "area_rate": geo["area_rate_m2ph"],
        "coating_in": coat["coat_kg_per_roll"],
        "substrate_in": coat["substrate_kg_per_roll"],
        "solids_in": solids_in,
        "product": waste["product_kg_per_roll"],
        "scrap": waste["waste_kg_per_roll"],
        "out": out,
        "residual": abs(solids_in - out),
    }


def report():
    base = load_params()
    perturbed = dict(base)
    perturbed["web_speed"] = 35.0          # different scale -> same per-m2 closure
    perturbed["web_width"] = 0.8

    print("=" * 70)
    print("Closed solids mass balance (coating + substrate == product + scrap)")
    print("=" * 70)
    all_ok = True
    for name, P in [("Pilot defaults", base), ("Perturbed scale", perturbed)]:
        s = closure(P)
        rolls_day = s["area_rate"] * 24 / s["area_m2"]
        ok = s["residual"] <= TOL * max(1.0, s["solids_in"])
        all_ok &= ok
        print(f"\n[{name}]  {s['area_rate']:.1f} m2/h, roll area {s['area_m2']:.1f} m2 "
              f"({rolls_day:.2f} rolls/day)")
        print(f"  IN   coating {s['coating_in']:.4f} + substrate {s['substrate_in']:.4f} "
              f"= {s['solids_in']:.6f} kg/roll")
        print(f"  OUT  product {s['product']:.4f} + scrap {s['scrap']:.4f} "
              f"= {s['out']:.6f} kg/roll")
        print(f"  residual {s['residual']:.2e}  ->  {'PASS' if ok else 'FAIL'}")

    print("\n" + "-" * 70)
    print(f"CLOSURE: {'PASS - solids close at both scales' if all_ok else 'FAIL'}")
    return all_ok


if __name__ == "__main__":
    raise SystemExit(0 if report() else 1)
