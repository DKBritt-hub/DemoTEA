"""Audit gate 6 (physical consistency) -- catches LATENT STUBS that sweeps miss.

A latent stub is an input that duplicates information the model already determines, then
silently disagrees with it. A parameter sweep can't catch this -- a disconnected input
still moves the output. The catch is the INVERSE of a sweep:

  A) IDENTITIES -- where the model knows a quantity two ways, assert they AGREE (single
     source of truth). Coating cost must read the SAME loading the mass balance uses; if
     someone re-introduced a disconnected coating-cost stub, the identity would break.

  B) COUPLINGS -- perturb an upstream physical input and require a downstream derived
     quantity to RESPOND. Physics/economics demand the link; its absence == a latent stub.

  C) PLAUSIBILITY tripwires -- bound the derived intermediates against external benchmarks.
     An implausible value trips the wire even if every coupling is wired.

When you add a layer, add its identities + couplings + bounds here. Exit 0 iff all hold.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_config                       # noqa: E402
from model import default_params, run_model          # noqa: E402

REL = 0.01      # a coupling must move its output >= 1% under a +20% input nudge
IDTOL = 1e-9


def main():
    cfg = load_config()
    P = default_params(cfg)
    base = run_model(P, cfg)
    problems = []

    def coating_cost(Q):
        return run_model(Q, cfg)["materials"]["coating_mat_m2"]

    def total_cost(Q):
        return run_model(Q, cfg)["full"]["total_m2"]

    def labor(Q):
        return run_model(Q, cfg)["conversion"]["labor_m2"]

    def annual(Q):
        return run_model(Q, cfg)["conversion"]["annual_m2"]

    def margin(Q):
        return run_model(Q, cfg)["value"]["margin_per_m2"]

    # ---- A) IDENTITIES: the model must not know coating mass/cost two disagreeing ways ----
    print("IDENTITIES (single source of truth -- the two ways must agree):")
    coat_kg_m2 = base["coat"]["coat_kg_per_m2"]
    id1 = abs(coat_kg_m2 - P["coat_loading"] / 1000.0)
    id2 = abs(base["materials"]["coating_mat_m2"]
              - (P["coat_loading"] / 1000.0) * P["coat_material_price"])
    for name, resid in [("mass-balance coat kg/m2 == loading/1000", id1),
                        ("coating $/m2 == loading/1000 x price", id2)]:
        ok = resid <= IDTOL
        if not ok:
            problems.append(f"identity broken: {name} (resid {resid:.2e}) -- latent stub")
        print(f"  {name:<42} resid {resid:.2e}  {'OK' if ok else 'BROKEN'}")

    # ---- B) COUPLINGS: each input MUST move its downstream derived quantity ----
    couplings = [
        ("coat_loading", coating_cost, "coating $/m2"),
        ("coat_material_price", coating_cost, "coating $/m2"),
        ("substrate_cost", total_cost, "total cost"),
        ("web_speed", annual, "annual good m2"),
        ("fte_count", labor, "labor $/m2"),
        ("selling_price", margin, "margin $/m2"),
    ]
    print("\nCOUPLINGS (downstream must respond to a +20% input nudge):")
    for k, fn, dlabel in couplings:
        b = fn(P)
        Q = dict(P)
        Q[k] = P[k] * 1.20
        rel = abs(fn(Q) - b) / max(abs(b), 1e-12)
        ok = rel >= REL
        if not ok:
            problems.append(f"coupling broken: {dlabel} does not respond to {k} "
                            f"(rel {rel:.2e}) -- possible latent stub")
        print(f"  {k:<22} -> {dlabel:<16} response {rel*100:7.2f}%  {'OK' if ok else 'BROKEN'}")

    # ---- C) PLAUSIBILITY tripwires on derived intermediates ----
    val, full, conv, mat = base["value"], base["full"], base["conversion"], base["materials"]
    materials_share = full["materials_m2"] / val["price_per_m2"]
    bounds = [
        ("coating material cost ($/m2)", mat["coating_mat_m2"], 0.1, 20.0),
        ("total cost ($/m2) vs ~$3-40 membrane band", full["total_m2"], 3.0, 40.0),
        ("materials as fraction of price", materials_share, 0.05, 0.95),
        ("annual good output (m2/yr)", conv["annual_m2"], 5000.0, 10_000_000.0),
    ]
    print("\nPLAUSIBILITY (derived intermediates within benchmark range):")
    for name, v, lo, hi in bounds:
        ok = lo <= v <= hi
        if not ok:
            problems.append(f"implausible: {name} = {v:.3f} outside [{lo}, {hi}]")
        print(f"  {name:<44} {v:12.3f}  [{lo}, {hi}]  {'OK' if ok else 'TRIP'}")

    print("\n" + "=" * 60)
    print("AUDIT GATE 6 -- physical consistency (latent-stub catcher)")
    print("=" * 60)
    if problems:
        print(f"  PROBLEMS ({len(problems)}):")
        for pr in problems:
            print(f"    - {pr}")
    else:
        print("  PASS -- identities agree; couplings intact; intermediates plausible")
    return not problems


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
