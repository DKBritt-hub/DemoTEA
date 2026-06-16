"""Mass balance for the Demo Co. R2R filtration-membrane line (illustrative).

Intensive-first: per-area quantities are computed first (they are scale-invariant),
then multiplied out to per-roll and per-time. A scale change is then a matter of
changing `web_speed` and `web_width` only; the per-m2 numbers must not move (that
invariance is itself a sanity check -- enforced by scale_check.py).

The membrane is a coated web: a functional coating (areal loading `coat_loading`,
g/m2) laid onto a support substrate (areal mass `substrate_areal`, g/m2). Solids in
per produced area == product solids (good area) + scrap solids (1 - yield). The
balance closes exactly (streams.py, the closed-balance gate). `coat_loading` is the
single source of truth for coating mass -- it drives BOTH the coating material cost
(tea.py) and this balance, so perturbing it must move both (consistency_check.py).
"""


def geometry(P):
    width_m = P["web_width"]                          # already meters
    area_m2 = P["roll_length"] * width_m
    return {
        "width_m": width_m,
        "area_m2": area_m2,
        "area_cm2": area_m2 * 1.0e4,
        "proc_time_h": P["roll_length"] / P["web_speed"],
        "area_rate_m2ph": P["web_speed"] * width_m,  # scale handle: speed x width
    }


def coating(P, geo):
    """Solids laid down. Per-m2 first (scale-invariant), then per-roll."""
    coat_kg_per_m2 = P["coat_loading"] / 1000.0               # g/m2 -> kg/m2
    substrate_kg_per_m2 = P["substrate_areal"] / 1000.0
    total_kg_per_m2 = coat_kg_per_m2 + substrate_kg_per_m2
    return {
        "coat_loading_g_m2": P["coat_loading"],
        "coat_kg_per_m2": coat_kg_per_m2,
        "substrate_kg_per_m2": substrate_kg_per_m2,
        "total_kg_per_m2": total_kg_per_m2,
        "coat_kg_per_roll": coat_kg_per_m2 * geo["area_m2"],
        "substrate_kg_per_roll": substrate_kg_per_m2 * geo["area_m2"],
        "total_kg_per_roll": total_kg_per_m2 * geo["area_m2"],
    }


def waste(P, geo, coat):
    """Scrap solids = (1 - yield) of produced solids; product solids = yield x produced.
    Closure: solids in == product + scrap (checked by streams.py)."""
    scrap_frac = 1.0 - P["oee_quality"]
    total_in_kg = coat["total_kg_per_roll"]
    waste_kg = total_in_kg * scrap_frac
    product_kg = total_in_kg * P["oee_quality"]
    return {
        "scrap_frac": scrap_frac,
        "waste_kg_per_roll": waste_kg,
        "product_kg_per_roll": product_kg,
        "total_in_kg_per_roll": total_in_kg,
        "waste_kg_per_m2": coat["total_kg_per_m2"] * scrap_frac,
    }


def mass_balance(P):
    geo = geometry(P)
    coat = coating(P, geo)
    w = waste(P, geo, coat)
    return {"geo": geo, "coat": coat, "waste": w}
