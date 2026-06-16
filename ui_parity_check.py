"""Audit gate 4 (UI <-> engine parity).

The dashboard must render the engine's output, never recompute it. The Streamlit app
reads engine.model.dashboard_view(P) and only formats the numbers. At the opening
defaults this proves:

  P1  every metric-card value equals the corresponding engine field (no re-derivation)
  P2  the cost waterfall's relative steps sum to the margin total
  P3  annual gross profit == margin/m2 x displayed annual m2 (the annual rollup is
      consistent with the per-m2 headline)

If the app ever starts doing its own arithmetic on engine outputs, these break.
Exit 0 iff parity holds (used by audit/run_gates.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from model import default_params, run_model, dashboard_view   # noqa: E402

TOL = 1e-9


def main():
    P = default_params()
    r = run_model(P)
    view = dashboard_view(P)
    c = view["cards"]
    full, val, conv = r["full"], r["value"], r["conversion"]

    card_ties = [
        ("cost_per_m2", c["cost_per_m2"], full["total_m2"]),
        ("revenue_per_m2", c["revenue_per_m2"], val["revenue_per_m2"]),
        ("margin_per_m2", c["margin_per_m2"], val["margin_per_m2"]),
        ("margin_pct", c["margin_pct"], val["margin_pct"]),
        ("annual_m2", c["annual_m2"], conv["annual_m2_scaled"]),
        ("annual_gross_profit", c["annual_gross_profit"], val["annual_gross_profit"]),
        ("oee", c["oee"], conv["oee"]),
        ("area_rate_m2ph", c["area_rate_m2ph"], conv["area_rate_m2ph"]),
    ]
    problems = []
    for name, shown, engine in card_ties:
        if abs(shown - engine) > TOL * max(1.0, abs(engine)):
            problems.append(f"P1 card '{name}': shown {shown} != engine {engine}")

    relatives = sum(v for _, v, m in view["waterfall"] if m == "relative")
    if abs(relatives - c["margin_per_m2"]) > TOL * max(1.0, abs(c["margin_per_m2"])):
        problems.append(f"P2 waterfall sum {relatives} != margin {c['margin_per_m2']}")

    if abs(c["annual_gross_profit"] - c["margin_per_m2"] * c["annual_m2"]) > TOL * max(
            1.0, abs(c["annual_gross_profit"])):
        problems.append("P3 annual GP != margin/m2 x annual m2")

    print("=" * 60)
    print("AUDIT GATE 4 -- UI <-> engine parity (opening defaults)")
    print("=" * 60)
    print(f"  cost     {c['cost_per_m2']:.4f} $/m2")
    print(f"  revenue  {c['revenue_per_m2']:.4f} $/m2")
    print(f"  margin   {c['margin_per_m2']:.4f} $/m2  ({c['margin_pct']*100:.1f}%)")
    print(f"  annual   {c['annual_m2']:,.0f} m2/yr -> GP ${c['annual_gross_profit']:,.0f}")
    print(f"  checks: P1 {len(card_ties)} cards, P2 waterfall sum, P3 annual rollup")
    if problems:
        print(f"  PROBLEMS ({len(problems)}):")
        for pr in problems:
            print(f"    - {pr}")
    else:
        print("  PASS -- dashboard renders engine output exactly; waterfall ties to margin")
    return not problems


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
