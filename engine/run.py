"""Console report + regression gate for the Demo Co. membrane TEA.

params -> mass_balance -> tea -> report. A public demo has no client spreadsheet to
reproduce, so the regression gate instead freezes the engine's own pilot headline as a
SYNTHETIC ANCHOR: the report recomputes the headline and checks it against the frozen
values, catching any unintended engine/config drift during maintenance. It also surfaces
a SENSITIVITY FLAGS block listing every soft input, so nothing is a buried assumption.
"""

from params import load_config, load_params
from mass_balance import mass_balance
from tea import tea

# Synthetic anchor: the pilot headline as designed (frozen from the engine itself).
# Re-freeze deliberately (and only deliberately) if the model is intentionally changed.
ANCHOR = {
    "cost_per_m2": 10.530872210482634,
    "materials_m2": 6.333333333333333,
    "conversion_m2": 4.1975388771493005,
    "margin_per_m2": -0.5308722104826344,
    "annual_m2_good": 117210.24,
}
REL_TOL = 1e-6
FLAG_STATUSES = {"illustrative", "estimate", "TBD", "client-provided"}


def report():
    cfg = load_config()
    P = load_params()
    mb = mass_balance(P)
    t = tea(P, mb)
    full, val, conv, geo = t["full"], t["value"], t["conversion"], mb["geo"]

    print("=" * 64)
    print("Demo Co. R2R Membrane TEA -- regression gate (pilot headline)")
    print("=" * 64)
    print(f"Basis: {geo['width_m']:.2f} m web x {P['web_speed']:.0f} m/h "
          f"-> {geo['area_rate_m2ph']:.2f} m2/h; {conv['annual_m2']:,.0f} good m2/yr")

    print("\nCost build-up (per good m2):")
    print(f"  Materials                {full['materials_m2']:8.4f}")
    print(f"  Conversion               {full['conversion_m2']:8.4f}")
    print(f"  Total cost               {full['total_m2']:8.4f}")
    print(f"  Revenue                  {val['revenue_per_m2']:8.4f}")
    print(f"  Margin                   {val['margin_per_m2']:8.4f}  "
          f"({val['margin_pct']*100:.1f}%)")

    actual = {
        "cost_per_m2": full["total_m2"],
        "materials_m2": full["materials_m2"],
        "conversion_m2": full["conversion_m2"],
        "margin_per_m2": val["margin_per_m2"],
        "annual_m2_good": conv["annual_m2"],
    }
    print("\nRegression vs synthetic anchor:")
    print(f"  {'metric':<16} {'actual':>16} {'anchor':>16}  result")
    all_ok = True
    for key, exp in ANCHOR.items():
        got = actual[key]
        ok = abs(got - exp) <= REL_TOL * max(abs(exp), 1e-9)
        all_ok &= ok
        print(f"  {key:<16} {got:>16.8g} {exp:>16.8g}  {'PASS' if ok else 'FAIL'}")
    print(f"\n  GATE: {'PASS - reproduces synthetic anchor' if all_ok else 'FAIL'}")

    # sensitivity flags
    flagged = [(k, meta) for k, meta in cfg["params"].items()
               if meta["status"] in FLAG_STATUSES]
    print("\n" + "-" * 64)
    print(f"SENSITIVITY FLAGS  ({len(flagged)} soft inputs surfaced)")
    print("-" * 64)
    by_status = {}
    for k, meta in flagged:
        by_status.setdefault(meta["status"], []).append(meta["label"])
    for status in ("TBD", "illustrative", "estimate", "client-provided"):
        items = by_status.get(status, [])
        if items:
            print(f"  [{status}] ({len(items)}): {', '.join(items)}")

    return all_ok


if __name__ == "__main__":
    ok = report()
    raise SystemExit(0 if ok else 1)
