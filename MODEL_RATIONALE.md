# Model Rationale — Demo Co. R2R Filtration Membrane TEA (illustrative)

What the model computes, what it currently says, and where the numbers come from. **Every
number is synthetic** — chosen to be representative and to tell a clear story, not to describe
any real company. The figures below are read directly from the engine (run `python
engine/model.py` and `python story_check.py` to reproduce them).

## What it computes

A roll-to-roll coated membrane is modeled intensive-first (per-m² quantities, which are
scale-invariant, then multiplied out by throughput):

1. **Mass balance** — coating loading (g/m²) + substrate areal mass close against product
   solids (good area) + scrap solids ((1 − yield) of produced area).
2. **Cost layers** (per good m²):
   - **Materials** — coating formulation (loading × price) + substrate, ÷ yield.
   - **Conversion** — labor, energy (fixed baseline + throughput-linked), overhead, disposal.
3. **Value** — revenue (selling price × good m²), margin, and annual gross profit.

## What it says now (pilot opening scenario)

Throughput basis: 1.2 m web × 20 m/h = 24 m²/h nameplate; OEE 0.598 (uptime 0.70 × performance
0.95 × yield 0.90) → **117,210 good m²/yr**.

| Cost line (per good m²) | $/m² |
|---|---:|
| Materials (coating + substrate) | 6.33 |
| Labor | 2.77 |
| Overhead | 1.11 |
| Energy | 0.31 |
| Disposal | 0.01 |
| **Total cost** | **10.53** |
| Revenue (selling price) | 10.00 |
| **Margin** | **−0.53  (−5.3%)** |

So at pilot scale the line is **just underwater** — typical of an early hard-tech process.

## The scale story (the centerpiece)

The production-scale selector dilutes the *fixed* per-m² stack (labor, overhead, baseline
power) as `capacity^(k−1)` with **k = 0.5**, and scales annual volume by `capacity`. The
*variable* floor (coating, substrate, throughput energy, disposal) does not move. Stages are
**Pilot 1× / Small commercial 5× / Full commercial 50×**:

| Stage | Margin | Annual gross profit |
|---|---:|---:|
| Pilot | −5.3% | −$62k |
| Small commercial | +17.2% | +$1.0M |
| Full commercial | +29.6% | +$17.4M |

**Near-breakeven at pilot → modestly profitable at small commercial → solidly profitable at
full commercial.** The fixed cost bars visibly shrink across stages while the variable floor
holds — that contrast is the lesson.

## Sensitivity scenarios (set the sliders to these)

The dashboard opens at the base case; drag the levers to reach the scenarios below (each
flows through the real engine). `python story_check.py` prints them.

- **Base case** — the table above.
- **Path to profit** (faster line, higher uptime + yield, cheaper coating): profitable even at
  **pilot (+25%)**, rising to +42% / ~$51M at full commercial. *Tighten operations and the unit
  economics work from the start.*
- **Downside** (price slips to $8/m², low uptime, dearer coating): −63% at pilot, still −27% at
  small commercial, and **still −7% even at full commercial**. *Scaling broken unit economics
  just loses money faster — scale is not a cure-all.*

## Where the numbers come from (provenance)

This is a demo, so provenance is honest about that. Every parameter carries a `status`:

- **`illustrative`** — synthetic process specifics (line speed, coating loading, coating price,
  selling price, headcount). Representative, not a real company's data.
- **`estimate`** — grounded in a public benchmark range (electricity ~$0.08–0.15/kWh, US
  manufacturing wages, operating calendar, yield/uptime ranges).
- **`constant`** — fixed modeling conventions (performance factor, paid hours/yr, substrate
  areal mass for the balance).

The same gap-awareness discipline we use on client work applies: nothing is a buried
assumption. Run `python engine/run.py` to see the **sensitivity-flags** block listing every
soft input, and the dashboard surfaces each as a labeled, movable slider.

## What is deliberately simple (demo scoping)

- Materials are lumped into coating + substrate (a real engagement would split the coating
  formulation into its components if the client needs that granularity).
- Overhead is a single annual line (rent + G&A + insurance), not broken out.
- Capital/depreciation is folded into the fixed stack via overhead rather than modeled as a
  capex/payback layer — kept light for a demo.
- The scale reframe credits only *fixed-cost dilution*; real variable improvements at scale
  (cheaper materials, OEE maturity) are left as unmodeled upside, so the story is conservative.
