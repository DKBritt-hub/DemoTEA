"""Deliverable entry point: the single function the dashboard calls.

    default_params()  -> param values at the opening (pilot) position. The UI seeds its
                         sliders from this. (deliverable_basis is an empty overlay for the
                         demo -- the param values ARE the opening scenario -- but the hook
                         is kept so this matches the shape of a real engagement build.)
    run_model(P)      -> runs the engine and returns every number the dashboard shows.
                         The UI renders THIS, never recomputes (ui_parity_check.py).
    dashboard_view(P) -> the exact cards + waterfall the dashboard renders.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from params import load_config   # noqa: E402
from mass_balance import mass_balance   # noqa: E402
from tea import tea   # noqa: E402

_OVERLAY_SKIP = {"_note"}   # non-param keys inside deliverable_basis


def deliverable_basis(cfg=None):
    cfg = cfg or load_config()
    return cfg["_meta"].get("deliverable_basis", {})


def default_params(cfg=None):
    """Param values at the opening position: `value` for every param, with any
    deliverable_basis overrides applied (none for the demo)."""
    cfg = cfg or load_config()
    P = {k: v["value"] for k, v in cfg["params"].items()}
    for k, v in deliverable_basis(cfg).items():
        if k in _OVERLAY_SKIP:
            continue
        if k in P:
            P[k] = v
    return P


def run_model(P, cfg=None):
    """Run the full engine and return every displayed quantity. Pure function of P."""
    cfg = cfg or load_config()
    mb = mass_balance(P)
    t = tea(P, mb)
    return {
        "geo": mb["geo"],
        "coat": mb["coat"],
        "waste": mb["waste"],
        "materials": t["materials"],
        "conversion": t["conversion"],
        "full": t["full"],
        "value": t["value"],
    }


def dashboard_view(P, cfg=None):
    """The exact numbers the dashboard renders, in one place (ui_parity_check.py
    verifies each equals the engine output). Waterfall is per-m2: revenue (+) then each
    cost (-), totaling to margin."""
    r = run_model(P, cfg)
    full, val, conv = r["full"], r["value"], r["conversion"]
    cards = {
        "cost_per_m2": full["total_m2"],
        "revenue_per_m2": val["revenue_per_m2"],
        "margin_per_m2": val["margin_per_m2"],
        "margin_pct": val["margin_pct"],
        "annual_m2": conv["annual_m2_scaled"],
        "annual_gross_profit": val["annual_gross_profit"],
        "annual_revenue": val["annual_revenue"],
        "oee": conv["oee"],
        "area_rate_m2ph": conv["area_rate_m2ph"],
    }
    waterfall = [
        ("Revenue", val["revenue_per_m2"], "relative"),
        ("Materials", -full["materials_m2"], "relative"),
        ("Labor", -conv["labor_m2"], "relative"),
        ("Energy", -conv["energy_m2"], "relative"),
        ("Overhead", -conv["overhead_m2"], "relative"),
        ("Disposal", -conv["disposal_m2"], "relative"),
        ("Margin", 0.0, "total"),
    ]
    return {"r": r, "cards": cards, "waterfall": waterfall}


def report():
    """Console view at opening (pilot) defaults (smoke test)."""
    P = default_params()
    r = run_model(P)
    full, val, conv, geo = r["full"], r["value"], r["conversion"], r["geo"]
    print("=" * 60)
    print("Demo Co. Membrane TEA -- opening (pilot) scenario")
    print("=" * 60)
    print(f"Basis: {geo['width_m']:.2f} m x {P['web_speed']:.0f} m/h "
          f"-> {geo['area_rate_m2ph']:.2f} m2/h; {conv['annual_m2']:,.0f} good m2/yr")
    print(f"\nCost:    {full['total_m2']:8.2f} $/m2")
    print(f"Revenue: {val['revenue_per_m2']:8.2f} $/m2")
    print(f"Margin:  {val['margin_per_m2']:8.2f} $/m2  ({val['margin_pct']*100:.1f}%)")
    print(f"Annual gross profit (pilot): ${val['annual_gross_profit']:,.0f}/yr")
    return r


if __name__ == "__main__":
    report()
