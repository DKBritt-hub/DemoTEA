"""Perturbation oracle: validate the engine's RESPONSE to input changes against a
predicted response class.

  EXACT  : output ratio must equal factor**exponent (asserted to 1e-7) -- the scale-exact
           geometry + coating relationships, including the per-m2 invariances (exponent 0).
  DIR    : cost/margin must move the predicted DIRECTION (or stay invariant), and be finite.

PASS 0 = invariance battery on the scale handles (speed/width/length): the per-m2 numbers
must not move. PASS 1 = exhaustive unit-wise (x2, x0.5) + round-trip on every lever.
Single pilot basis (the demo has no dual lab/target conventions). Exit 0 iff no failures.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_params, load_meta          # noqa: E402
from model import run_model                          # noqa: E402

RTOL = 1e-7

EXACT_OUTPUTS = ["area_m2", "area_rate", "proc_time", "coat_kg_m2", "coating_mat_m2"]
DIR_OUTPUTS = ["total_cost", "margin"]

# EXACT exponent oracle: output := base * factor**exp (absent entries => exp 0 = invariant)
EXACT = {
    "roll_length":         {"area_m2": 1, "proc_time": 1},
    "web_width":           {"area_m2": 1, "area_rate": 1},
    "web_speed":           {"area_rate": 1, "proc_time": -1},
    "coat_loading":        {"coat_kg_m2": 1, "coating_mat_m2": 1},
    "coat_material_price": {"coating_mat_m2": 1},
}

# DIR oracle: sign of (total_cost, margin) response. +1 up, -1 down, 0 invariant.
DIR = {
    "web_speed":               {"total_cost": -1, "margin": +1},
    "web_width":               {"total_cost": -1, "margin": +1},
    "roll_length":             {"total_cost": 0, "margin": 0},
    "operating_hours_per_day": {"total_cost": -1, "margin": +1},
    "operating_days_per_year": {"total_cost": -1, "margin": +1},
    "oee_availability":        {"total_cost": -1, "margin": +1},
    "oee_quality":             {"total_cost": -1, "margin": +1},
    "coat_loading":            {"total_cost": +1, "margin": -1},
    "coat_material_price":     {"total_cost": +1, "margin": -1},
    "substrate_cost":          {"total_cost": +1, "margin": -1},
    "fte_count":               {"total_cost": +1, "margin": -1},
    "wage":                    {"total_cost": +1, "margin": -1},
    "labor_overhead":          {"total_cost": +1, "margin": -1},
    "electricity_price":       {"total_cost": +1, "margin": -1},
    "energy_intensity":        {"total_cost": +1, "margin": -1},
    "fixed_power_kw":          {"total_cost": +1, "margin": -1},
    "overhead_annual":         {"total_cost": +1, "margin": -1},
    "disposal_rate":           {"total_cost": +1, "margin": -1},
    "selling_price":           {"total_cost": 0, "margin": +1},
}


def outputs(P):
    r = run_model(P)
    geo, coat, mat, full, val = r["geo"], r["coat"], r["materials"], r["full"], r["value"]
    return {
        "area_m2": geo["area_m2"],
        "area_rate": geo["area_rate_m2ph"],
        "proc_time": geo["proc_time_h"],
        "coat_kg_m2": coat["coat_kg_per_m2"],
        "coating_mat_m2": mat["coating_mat_m2"],
        "total_cost": full["total_m2"],
        "margin": val["margin_per_m2"],
    }


def perturb(P, key, factor):
    Q = dict(P)
    Q[key] = P[key] * factor
    return Q


def approx(a, b, rtol=RTOL):
    if b == 0:
        return abs(a) <= rtol
    return abs(a - b) / abs(b) <= rtol


def check_param(P, base, key, factor):
    out = outputs(perturb(P, key, factor))
    rows, fails = [], 0
    exp_map = EXACT.get(key, {})
    dir_map = DIR.get(key, {})

    for o in EXACT_OUTPUTS:
        exp = exp_map.get(o, 0)
        want = base[o] * (factor ** exp)
        if not approx(out[o], want):
            fails += 1
            cls = "inv" if exp == 0 else f"E^{exp}"
            rows.append(f"    FAIL {key} x{factor} -> {o}: got {out[o]:.8g}, "
                        f"want {want:.8g} ({cls})")

    for o in DIR_OUTPUTS:
        got, b0 = out[o], base[o]
        if not math.isfinite(got):
            fails += 1
            rows.append(f"    FAIL {key} x{factor} -> {o}: not finite ({got})")
            continue
        spec = dir_map.get(o, 0)
        if spec == 0:
            if not approx(got, b0):
                fails += 1
                rows.append(f"    FAIL {key} x{factor} -> {o}: expected invariant, "
                            f"moved {b0:.6g}->{got:.6g}")
        else:
            if approx(got, b0):
                continue
            want_up = (factor > 1) == (spec > 0)
            if (got > b0) != want_up:
                fails += 1
                rows.append(f"    FAIL {key} x{factor} -> {o}: sign wrong "
                            f"({b0:.6g}->{got:.6g}, expected {'up' if want_up else 'down'})")
    return rows, fails


def main():
    P = load_params()
    meta = load_meta()
    base = outputs(P)
    fails = 0

    print("=" * 72)
    print("PERTURBATION ORACLE (membrane, pilot basis)")
    print("=" * 72)

    print("\nPASS 0 - invariance battery (scale handles: per-m2 must not move)")
    for key in ["web_speed", "web_width", "roll_length"]:
        for f in (2.0, 0.5):
            rows, fl = check_param(P, base, key, f)
            fails += fl
            print(f"  {key:<16} x{f:<4} : {'ok' if fl == 0 else f'{fl} FAIL'}")
            for r in rows:
                print(r)

    print("\nPASS 1 - exhaustive unit-wise + round-trip")
    for key, m in meta.items():
        if not isinstance(m.get("slider"), dict) or m.get("status") == "constant":
            continue
        pf = 0
        for f in (2.0, 0.5):
            rows, fl = check_param(P, base, key, f)
            pf += fl
            for r in rows:
                print(r)
        rt = outputs(perturb(perturb(P, key, 2.0), key, 0.5))
        if not all(approx(rt[o], base[o]) for o in EXACT_OUTPUTS):
            pf += 1
            print(f"    FAIL {key}: round-trip did not restore baseline")
        fails += pf
        print(f"  {m['label']:<26} ({m['tier']:<8}) : {'ok' if pf == 0 else f'{pf} FAIL'}")

    print("\n" + "=" * 72)
    print(f"TOTAL FAILURES: {fails}  ->  {'ALL PASS' if fails == 0 else 'RED'}")
    print("=" * 72)
    return fails


if __name__ == "__main__":
    raise SystemExit(0 if main() == 0 else 1)
