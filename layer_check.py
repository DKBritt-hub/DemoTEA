"""Audit gate 3 (layer-boundary reconciliation).

When a cost/revenue layer lands it must not silently drop or double-count across its
boundary. At the pilot defaults this proves:

  R1  full total       == materials + conversion subtotal            (no drop)
  R2  conversion       == labor + energy + overhead + disposal       (parts sum)
  R3  energy           == fixed baseline + throughput-linked         (parts sum)
  R4  materials (good) == coating + substrate (good)                 (parts sum)
  R5  disposal mass basis == mass-balance scrap stream              (cross-layer tie:
        the disposal COST prices the SAME scrap mass the closed balance routes to waste)
  R6  margin           == revenue - cost                             (value layer)
  R7  annual gross profit == margin/m2 x annual good m2              (annual rollup)

Exit 0 iff all reconciliations hold. Any new layer adds its boundary check here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_params          # noqa: E402
from mass_balance import mass_balance     # noqa: E402
from tea import tea                        # noqa: E402

TOL = 1e-9


def main():
    P = load_params()
    mb = mass_balance(P)
    t = tea(P, mb)
    mat, conv, full, val = t["materials"], t["conversion"], t["full"], t["value"]
    area = mb["geo"]["area_m2"]
    Q = conv["oee_quality"]

    r1 = abs(full["total_m2"] - (full["materials_m2"] + conv["conversion_m2"]))
    parts = conv["labor_m2"] + conv["energy_m2"] + conv["overhead_m2"] + conv["disposal_m2"]
    r2 = abs(conv["conversion_m2"] - parts)
    r3 = abs(conv["energy_m2"] - (conv["energy_fixed_m2"] + conv["energy_var_m2"]))
    r4 = abs(full["materials_m2"] - (full["coating_mat_m2"] + full["substrate_m2"]))

    # disposal cost prices the mass-balance scrap stream. disposal_m2 is per GOOD m2
    # (/Q); back out its implied PRODUCED scrap mass and compare to the mass balance.
    disposal_scrap_kg_m2 = (conv["disposal_m2"] / P["disposal_rate"]) * Q
    r5 = abs(disposal_scrap_kg_m2 - mb["waste"]["waste_kg_per_m2"])

    r6 = abs(val["margin_per_m2"] - (val["revenue_per_m2"] - val["cost_per_m2"]))
    r7 = abs(val["annual_gross_profit"] - val["margin_per_m2"] * val["annual_m2"])

    checks = [
        ("R1 full == materials + conversion", r1),
        ("R2 conversion == sum(parts)", r2),
        ("R3 energy == fixed + var", r3),
        ("R4 materials == coating + substrate", r4),
        ("R5 disposal mass == scrap stream", r5),
        ("R6 margin == revenue - cost", r6),
        ("R7 annual GP == margin/m2 x annual m2", r7),
    ]

    print("=" * 66)
    print("AUDIT GATE 3 -- layer reconciliation (pilot defaults)")
    print("=" * 66)
    print("\nFull cost build-up ($/m2 per GOOD m2):")
    print(f"  materials (coating+substrate)  {full['materials_m2']:8.4f}")
    print(f"    - coating                    {full['coating_mat_m2']:8.4f}")
    print(f"    - substrate                  {full['substrate_m2']:8.4f}")
    print(f"  labor                          {conv['labor_m2']:8.4f}")
    print(f"  energy                         {conv['energy_m2']:8.4f}"
          f"   (fixed {conv['energy_fixed_m2']:.4f} + var {conv['energy_var_m2']:.4f})")
    print(f"  overhead                       {conv['overhead_m2']:8.4f}")
    print(f"  disposal                       {conv['disposal_m2']:8.4f}")
    print(f"  {'-'*40}")
    print(f"  TOTAL cost                     {full['total_m2']:8.4f}  $/m2")
    print(f"\n  Throughput: {conv['area_rate_m2ph']:.2f} m2/h x {conv['annual_hours']:.0f} h/yr "
          f"x OEE {conv['oee']:.3f} = {conv['annual_m2']:,.0f} good m2/yr")
    print(f"  Revenue {val['revenue_per_m2']:.2f}  Margin {val['margin_per_m2']:.2f} $/m2 "
          f"({val['margin_pct']*100:.1f}%)  Annual GP ${val['annual_gross_profit']:,.0f}")

    print("\n" + "-" * 66)
    print("RECONCILIATIONS")
    print("-" * 66)
    allok = True
    for name, resid in checks:
        ok = resid <= TOL * max(1.0, abs(full["total_m2"]))
        allok &= ok
        print(f"  {name:<42} resid {resid:.2e}  {'PASS' if ok else 'FAIL'}")
    print("-" * 66)
    print(f"  GATE 3: {'PASS' if allok else 'FAIL'}")
    return allok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
