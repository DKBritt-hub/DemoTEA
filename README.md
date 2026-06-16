# Demo Co. — R2R Filtration Membrane TEA (illustrative)

A public **demonstration** techno-economic model of a roll-to-roll coated filtration-membrane
line, with a config-driven Streamlit dashboard. It is a sales/promotional mock-up of the kind
of auditable TEA + interactive dashboard we build for clients.

> **All data here is synthetic.** No real company, process, or proprietary information is
> represented. The numbers are chosen to be *representative* and to tell a clear story, not to
> describe any actual product.

## What it shows

- A transparent, layered Python engine (mass balance → cost layers → value) behind a
  config-driven dashboard — every slider is generated from `config/params.json` metadata, and
  the screen renders the engine's output directly (it never recomputes).
- A **production-scale reframe**: a Pilot / Small commercial / Full commercial selector that
  dilutes the *fixed* cost stack (labor, overhead, baseline power) per m² and scales annual
  volume, while the *variable* floor (coating materials, substrate, throughput energy) stays
  put. This drives the story: **near-breakeven at pilot → modestly profitable at small
  commercial → solidly profitable at full commercial.**
- **Scenario presets** (Base case / Path to profit / Downside) that snap the levers to tell the
  "improve X and you're profitable; let Y slip and you're not" story — each flows through the
  real engine.
- Provenance tags on every parameter, an **editor mode** (the authorized write path we give
  client teams), and a **12-gate audit suite** that proves the model is internally consistent.

## Layout

```
config/params.json     Single source of truth: every parameter's value + metadata
                       (slider min/max/step, status, category, tier, source, change_log).
engine/
  params.py            Loads config -> values (engine) and metadata (UI / edit-mode)
  mass_balance.py      Intensive-first solids balance (coating + substrate -> product + scrap)
  tea.py               Cost layers: materials, conversion (labor/energy/overhead/disposal),
                       full cost, value (revenue / margin / annual gross profit)
  model.py             Entry point: default_params(), run_model(P), dashboard_view(P)
  run.py               Console report + synthetic-anchor regression gate
  edit_mode.py         Sanctioned write-back to config (change_log + guards)
  publish.py           Editor Save path (sanity-gated apply + optional git push)
streamlit_app.py       Config-driven dashboard (sliders generated from metadata)
audit/run_gates.py     The audit gate suite — run this
*.py (root)            The individual check scripts run_gates.py invokes
story_check.py         Dev aid: prints the margin story across stages + presets (not a gate)
```

## Run

```
python audit/run_gates.py     # audit — exit 0 = ALL GREEN (12 gates)
python engine/model.py        # console view of the pilot scenario
python story_check.py         # the pilot->commercial story + scenario presets
streamlit run streamlit_app.py    # the dashboard (local)
```

The dashboard is **open — no password** (it is a public demo). Editor mode (the write feature)
is gated by a separate editor password set only in the host's secrets manager; the public
deploy sets none, so viewer changes are always session-only.

## Audit

One command proves the model is intact: `python audit/run_gates.py` — 12 checks, exit-code
based, green only if all pass. It enforces a synthetic-anchor regression, mass-balance closure,
layer reconciliation, UI↔engine parity, edit-mode integrity, physical consistency (the
latent-stub catcher), and bounds safety. A change is trustworthy iff this stays green. See
`AGENTS.md`.
