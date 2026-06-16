"""Cost + value layers for the Demo Co. R2R membrane line (illustrative).

Layered, pure functions over a computed mass balance:

    materials  -- coating formulation + substrate, per m2 (variable, scale-invariant)
    conversion -- labor, energy, overhead, disposal, per good m2 (fixed + variable)
    full       -- materials/yield + conversion, per good m2
    value      -- revenue, margin, annual gross profit (the headline)

Two production-scale view factors are injected by the dashboard (default 1.0, so every
gate sees pilot):
    fixed_scale  = capacity_x^(k-1)  -- dilutes the per-m2 FIXED stack to approximate
                   commercial scale-up; the VARIABLE stack is scale-invariant and untouched.
    capacity_x   -- multiplies displayed annual VOLUME (so annual profit grows with scale).
"""


def material_costs(P, mb):
    """Coating formulation + substrate, per PRODUCED m2 (variable, scale-invariant).

    coating $/m2 = coat_loading (g/m2) x coat_material_price ($/kg) / 1000. This is the
    one place coating cost is computed and it reads the same loading the mass balance
    uses -- a single source of truth, not a disconnected stub (consistency_check.py
    perturbs coat_loading and requires this to move)."""
    coating_mat_m2 = mb["coat"]["coat_kg_per_m2"] * P["coat_material_price"]
    substrate_m2 = P["substrate_cost"]
    return {
        "coating_mat_m2": coating_mat_m2,
        "substrate_m2": substrate_m2,
        "materials_produced_m2": coating_mat_m2 + substrate_m2,
    }


def conversion_costs(P, mb):
    """Conversion cost layer, per good m2. Fixed classes (labor, baseline power,
    overhead) amortize over annual good m2 and are diluted by `fixed_scale` at scale;
    variable classes (throughput energy, disposal) are per-m2-invariant (divided by
    yield, since scrap consumed them but is not sold)."""
    geo = mb["geo"]
    area_m2 = geo["area_m2"]
    area_rate = geo["area_rate_m2ph"]
    annual_hours = P["operating_hours_per_day"] * P["operating_days_per_year"]
    annual_m2_nameplate = area_rate * annual_hours

    A, Pf, Q = P["oee_availability"], P["oee_performance"], P["oee_quality"]
    oee = A * Pf * Q
    annual_m2_good = annual_m2_nameplate * oee

    fs = P.get("fixed_scale", 1.0)             # fixed-cost dilution at scale (1.0 at pilot)
    cap_x = P.get("capacity_x", 1.0)           # displayed-volume multiple at scale

    # labor (fixed annual -> per good m2, diluted at scale)
    labor_annual = (P["fte_count"] * P["wage"] * (1 + P["labor_overhead"])
                    * P["fte_hours_per_year"])
    labor_m2 = labor_annual / annual_m2_good * fs

    # energy: fixed baseline (diluted) + throughput-linked (variable -> /yield)
    energy_fixed_annual = P["fixed_power_kw"] * annual_hours * P["electricity_price"]
    energy_fixed_m2 = energy_fixed_annual / annual_m2_good * fs
    energy_var_m2 = P["energy_intensity"] * P["electricity_price"] / Q
    energy_m2 = energy_fixed_m2 + energy_var_m2

    # overhead (fixed annual -> per good m2, diluted)
    overhead_m2 = P["overhead_annual"] / annual_m2_good * fs

    # disposal (variable scrap mass -> per good m2 via yield)
    disposal_m2 = mb["waste"]["waste_kg_per_roll"] * P["disposal_rate"] / area_m2 / Q

    return {
        "annual_hours": annual_hours,
        "annual_m2_nameplate": annual_m2_nameplate,
        "annual_m2": annual_m2_good,                 # good (sellable) m2/yr at pilot
        "annual_m2_scaled": annual_m2_good * cap_x,  # displayed volume at the chosen stage
        "oee": oee,
        "oee_availability": A, "oee_performance": Pf, "oee_quality": Q,
        "area_rate_m2ph": area_rate,
        # per-good-m2 line items
        "labor_m2": labor_m2,
        "energy_m2": energy_m2,
        "energy_fixed_m2": energy_fixed_m2,
        "energy_var_m2": energy_var_m2,
        "overhead_m2": overhead_m2,
        "disposal_m2": disposal_m2,
        "conversion_m2": labor_m2 + energy_m2 + overhead_m2 + disposal_m2,
        # annual fixed totals (transparency)
        "labor_annual": labor_annual,
        "energy_fixed_annual": energy_fixed_annual,
        "overhead_annual": P["overhead_annual"],
    }


def full_cost(P, mb):
    """Full per-GOOD-m2 cost = materials (variable, /yield) + conversion.

    Materials are consumed per produced m2; scrap (1 - yield) was bought but not sold,
    so per-good-m2 materials = produced materials / yield. Conversion already carries
    its own yield treatment."""
    mat = material_costs(P, mb)
    conv = conversion_costs(P, mb)
    Q = P["oee_quality"]
    materials_good_m2 = mat["materials_produced_m2"] / Q
    return {
        "materials_m2": materials_good_m2,
        "coating_mat_m2": mat["coating_mat_m2"] / Q,
        "substrate_m2": mat["substrate_m2"] / Q,
        "conversion_m2": conv["conversion_m2"],
        "total_m2": materials_good_m2 + conv["conversion_m2"],
    }


def value_metrics(P, mb):
    """Revenue + margin + annual gross profit. Membrane sells per m2, so revenue/m2 is
    simply the selling price; margin/m2 = price - full cost/m2. Annual figures use the
    displayed (scaled) volume so they grow with the production-scale selector."""
    full = full_cost(P, mb)
    conv = conversion_costs(P, mb)
    cost_m2 = full["total_m2"]
    price = P["selling_price"]
    revenue_m2 = price
    margin_m2 = revenue_m2 - cost_m2
    margin_pct = margin_m2 / revenue_m2 if revenue_m2 else float("nan")

    annual_m2 = conv["annual_m2_scaled"]
    return {
        "cost_per_m2": cost_m2,
        "price_per_m2": price,
        "revenue_per_m2": revenue_m2,
        "margin_per_m2": margin_m2,
        "margin_pct": margin_pct,
        "annual_m2": annual_m2,
        "annual_revenue": revenue_m2 * annual_m2,
        "annual_gross_profit": margin_m2 * annual_m2,
    }


def tea(P, mb):
    """Assemble the cost + value view over a computed mass balance."""
    return {
        "materials": material_costs(P, mb),
        "conversion": conversion_costs(P, mb),
        "full": full_cost(P, mb),
        "value": value_metrics(P, mb),
    }
