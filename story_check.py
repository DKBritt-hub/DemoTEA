"""Scale-story + scenario-preset check (tuning aid, not a gate)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_config            # noqa: E402
from model import default_params, run_model   # noqa: E402

cfg = load_config()
ss = cfg["_meta"]["scale_stages"]
k = ss["exponent"]
base = default_params(cfg)

PRESETS = {
    "Base case (as-built)": {},
    "Path to profit": {"web_speed": 32.0, "oee_availability": 0.85,
                       "oee_quality": 0.96, "coat_material_price": 120.0},
    "Downside": {"selling_price": 8.0, "oee_availability": 0.55,
                 "coat_material_price": 190.0},
}


def margins(overrides):
    out = []
    for s in ss["stages"]:
        cx = s["capacity_x"]
        P = dict(base)
        P.update(overrides)
        P["fixed_scale"] = float(cx) ** (k - 1.0)
        P["capacity_x"] = float(cx)
        v = run_model(P)["value"]
        out.append((s["name"], v["margin_pct"] * 100, v["annual_gross_profit"]))
    return out


print(f"k={k}, stages={[(s['name'], s['capacity_x']) for s in ss['stages']]}\n")
for name, ov in PRESETS.items():
    print(f"{name}:")
    for stage, mp, gp in margins(ov):
        print(f"   {stage:<18} margin {mp:6.1f}%   annual GP ${gp:>14,.0f}")
    print()
