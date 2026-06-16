# AGENTS.md — working on the Demo Co. Membrane TEA

How this repo is structured and how to change it **safely**. This is an illustrative public
demo (synthetic data), but it is built to the same discipline as a client deliverable: the
audit-gate suite is the safe-change contract.

## 1. The contract

> **After any change to `engine/`, `config/`, or a check script, `python audit/run_gates.py`
> must print `ALL GREEN` (exit 0).** A change is trustworthy if and only if the suite is green.
> Do not loosen a tolerance to turn a gate green; fix the cause or, if the change is intentional,
> re-derive the gate deliberately (see §4).

Run it from the repo root:

```
python audit/run_gates.py
```

## 2. The 12 gates (what each proves)

| Gate | File | Proves |
|---|---|---|
| Regression (synthetic anchor) | `engine/run.py` | engine reproduces the frozen pilot headline |
| Mass-balance rows | `validate_massbalance.py` | each balance intermediate equals its expected value |
| Closed mass balance | `streams.py` | coating + substrate == product + scrap (closes at any scale) |
| Layer reconciliation | `layer_check.py` | each cost/value layer sums with no drop/double-count |
| UI↔engine parity | `ui_parity_check.py` | the dashboard renders engine output exactly |
| Edit-mode round-trip | `round_trip_check.py` | write→reload→identical; invalid edits refused |
| Editor meta + publish | `meta_publish_check.py` | meta edits + sanity-gated save + git publish |
| Physical consistency | `consistency_check.py` | **identities agree, couplings respond — the latent-stub catcher** |
| Bounds finite | `bounds_finite_check.py` | every slider min/max yields a finite headline |
| Perturbation oracle | `perturbation.py` | response classes (exact scaling / sign) hold |
| Scale invariance | `scale_check.py` | variable per-m² invariant; fixed dilutes; throughput scales |
| Param provenance | `audit/provenance_check.py` | every param tagged, sourced; every lever slider valid |

A headless dashboard smoke test (`app_boot_test.py`) runs the whole app via Streamlit's
`AppTest`; it needs `streamlit` installed and is kept out of the core suite so the gates stay
dependency-light (engine is pure stdlib).

## 3. Edit-risk tiers

**🟢 Green — safe; the gates catch regressions.**
- Change a parameter's **value** or **slider range** (in `config/params.json`, or via the
  dashboard's editor mode — the sanctioned path). Re-run the suite.
- **Add a parameter**: give it the full metadata block (the provenance gate enforces it); its
  slider appears in the UI automatically, grouped by `category`/`tier`.
- Cosmetic dashboard changes (labels, layout, colors) in `streamlit_app.py`.

**🟡 Yellow — allowed, but re-run the suite and eyeball the story.**
- Change the **scale stages** or exponent `k` in `_meta.scale_stages` (this moves the
  pilot→commercial story — re-check with `python story_check.py`).
- **Re-freeze the regression anchor** (`ANCHOR` in `engine/run.py`) — only when you have
  *intentionally* changed the model and confirmed the new headline is correct.

**🔴 Red — do not, without re-deriving the audit.**
- Change the **engine math or layer structure** (`mass_balance.py`, `tea.py`) without adding/
  updating the matching reconciliation + consistency checks.
- **Remove a gate**, or loosen a tolerance to force green.
- Introduce an input that **duplicates** a quantity the model already determines (a *latent
  stub*) without extending `consistency_check.py` to assert the two agree.

## 4. Notes

- **Edit mode is the only sanctioned config mutator.** `engine/edit_mode.py` validates the
  provenance invariants *before* writing, appends a `change_log` entry, and writes atomically.
  Nothing should write `config/params.json` directly.
- **The synthetic anchor** (`engine/run.py`) is the demo's stand-in for a client spreadsheet:
  it freezes the engine's own pilot headline so accidental drift is caught. It is the one place
  a headline number is hardcoded — change it only deliberately.
- **Secrets**: none are needed for the public viewer app. `.streamlit/secrets.toml` is
  gitignored; any editor password lives only in the host's secrets manager.
