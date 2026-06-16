"""Demo Co. R2R Filtration Membrane TEA -- dashboard (illustrative).

A public sales/demo mock-up of the techno-economic model + dashboard we build for clients.
ALL DATA IS SYNTHETIC. The app is open (no password). Every slider is generated from
config/params.json metadata and the app computes via engine.model.dashboard_view -> the
SAME audited engine the gate suite checks; it never recomputes (audit gate 4).

Run locally:  streamlit run streamlit_app.py
Deploy:       push to GitHub, connect at share.streamlit.io, main file streamlit_app.py
"""
import sys
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_config, CONFIG_PATH   # noqa: E402
from model import default_params, dashboard_view   # noqa: E402
from publish import save_and_publish          # noqa: E402

st.set_page_config(page_title="Demo Co. Membrane TEA", layout="wide",
                   initial_sidebar_state="expanded")

CFG = load_config()
PARAMS = CFG["params"]
DEFAULTS = default_params(CFG)


# -- Helpers -----------------------------------------------------------------------
def _slider_nums(sl, default):
    raw = [sl["min"], sl["max"], sl["step"], default]
    all_int = all(float(x).is_integer() for x in raw)
    cast = int if all_int else float
    return cast(sl["min"]), cast(sl["max"]), cast(sl["step"]), cast(default)


def _is_lever(meta):
    return meta.get("status") != "constant" and meta.get("tier") not in ("fixed", "negligible") \
        and isinstance(meta.get("slider"), dict)


def _fmt_usd(x):
    return f"${x:,.2f}"


def _secret(table, key=None):
    """Defensive st.secrets access -- a public deploy has no secrets file; return {} then."""
    try:
        t = st.secrets.get(table, {})
    except Exception:                          # noqa: BLE001 - no secrets file on open deploy
        return {}
    return t


HIDDEN_KEYS = set(CFG["_meta"].get("hidden_factors", {}).get("keys", []))
LEVER_KEYS = [k for k, m in PARAMS.items() if _is_lever(m) and k not in HIDDEN_KEYS]
PINNED_DEFAULT = [k for k in CFG["_meta"].get("pinned_default", {}).get("keys", [])
                  if k in LEVER_KEYS]
MINOR_KEYS = [k for k in CFG["_meta"].get("minor_factors", {}).get("keys", [])
              if k in LEVER_KEYS]

# Scenario presets: snap the operating levers to tell the story (each flows through the real
# engine -- presets only set slider values, they never fake an output). Keys absent from a
# preset reset to their config default.
PRESETS = {
    "Base case (as-built)": {},
    "Path to profit": {"web_speed": 32.0, "oee_availability": 0.85,
                       "oee_quality": 0.96, "coat_material_price": 120.0},
    "Downside": {"selling_price": 8.0, "oee_availability": 0.55,
                 "coat_material_price": 190.0},
}


# Each lever's live value persists in a NON-widget canonical key `v_{key}` (survives a twin
# not being rendered). Two twins may show one param: pinned mirror ("top") + its group ("grp").
def _seed_state():
    if "pinned" not in st.session_state:
        st.session_state["pinned"] = list(PINNED_DEFAULT)
    for key in LEVER_KEYS:
        if f"v_{key}" not in st.session_state:
            _, _, _, val = _slider_nums(PARAMS[key]["slider"], DEFAULTS[key])
            st.session_state[f"v_{key}"] = val


def _commit(key, wk):
    st.session_state[f"v_{key}"] = st.session_state[wk]


def _toggle_pin(key, pin):
    pinned = st.session_state["pinned"]
    if pin and key not in pinned:
        pinned.append(key)
    elif not pin and key in pinned:
        pinned.remove(key)


def _reset_values():
    for key in LEVER_KEYS:
        _, _, _, val = _slider_nums(PARAMS[key]["slider"], DEFAULTS[key])
        st.session_state[f"v_{key}"] = val


def _apply_preset(name):
    """Reset all levers to default, then apply the named preset's overrides."""
    overrides = PRESETS[name]
    for key in LEVER_KEYS:
        _, _, _, val = _slider_nums(PARAMS[key]["slider"], DEFAULTS[key])
        st.session_state[f"v_{key}"] = overrides.get(key, val)


def _slider_row(key, suffix):
    meta = PARAMS[key]
    lo, hi, step, _ = _slider_nums(meta["slider"], DEFAULTS[key])
    wk = f"{key}__{suffix}"
    cast = type(lo)
    seeded = cast(min(max(st.session_state[f"v_{key}"], lo), hi))
    st.session_state[f"v_{key}"] = seeded
    st.session_state[wk] = seeded
    is_pinned = key in st.session_state["pinned"]
    col_s, col_b = st.columns([0.85, 0.15], vertical_alignment="bottom")
    with col_s:
        st.slider(f"{meta['label']} ({meta['unit']})", lo, hi, step=step, key=wk,
                  on_change=_commit, args=(key, wk))
    with col_b:
        st.button("📌" if is_pinned else "📍", key=f"tack_{suffix}_{key}", width="stretch",
                  help="Unpin" if is_pinned else "Pin to top",
                  on_click=_toggle_pin, args=(key, not is_pinned))


_seed_state()


# -- Sidebar -----------------------------------------------------------------------
_cats = []
for meta in PARAMS.values():
    if _is_lever(meta) and meta["category"] not in _cats:
        _cats.append(meta["category"])

with st.sidebar:
    _stages = CFG["_meta"].get("scale_stages", {})
    _stage_list = _stages.get("stages") or [{"name": "Pilot", "capacity_x": 1}]
    _exponent = float(st.session_state.get("ed_scale_exponent", _stages.get("exponent", 0.5)))
    _stage_name = st.radio("Production scale", [s["name"] for s in _stage_list],
                           key="prod_scale",
                           help="Approximate scale-up: dilutes FIXED costs (labor, overhead, "
                                "baseline power) per m² and scales annual volume. VARIABLE "
                                "costs per m² are scale-invariant and do not move.")
    _cap_x = next((s["capacity_x"] for s in _stage_list if s["name"] == _stage_name), 1)
    fixed_scale = float(_cap_x) ** (_exponent - 1.0)
    st.divider()

    st.markdown("### Scenarios")
    st.caption("Snap the levers to a story; then drag to explore.")
    for nm in PRESETS:
        st.button(nm, key=f"preset_{nm}", width="stretch",
                  on_click=_apply_preset, args=(nm,))
    st.divider()

    st.markdown("## Pinned levers")
    st.caption("Tack (📍) any slider below to add it here; tack (📌) again to remove.")
    if st.session_state["pinned"]:
        for key in st.session_state["pinned"]:
            _slider_row(key, "top")
    else:
        st.caption("_None pinned — tack a slider from the groups below._")
    st.button("↺ Reset to default pins", key="reset_pins",
              on_click=lambda: st.session_state.update(pinned=list(PINNED_DEFAULT)))

    st.divider()
    st.markdown("### All parameters")
    st.button("↺ Reset values to defaults", key="reset_values", on_click=_reset_values)
    for cat in _cats:
        keys = [k for k in LEVER_KEYS
                if PARAMS[k]["category"] == cat and k not in MINOR_KEYS]
        if not keys:
            continue
        with st.expander(cat, expanded=False):
            for key in keys:
                _slider_row(key, "grp")

    if MINOR_KEYS:
        with st.expander("Minor factors", expanded=False):
            st.caption("Small impact on the headline; here to reduce clutter.")
            for key in MINOR_KEYS:
                _slider_row(key, "grp")


# -- Main area ---------------------------------------------------------------------
st.markdown("## Demo Co. — R2R Filtration Membrane TEA")
st.caption("Illustrative demonstration model · **synthetic data, not a real company** · "
           "shows the auditable techno-economic engine + dashboard we build for clients.")

P = dict(DEFAULTS)
for key in LEVER_KEYS:
    P[key] = st.session_state[f"v_{key}"]
P["fixed_scale"] = fixed_scale
P["capacity_x"] = float(_cap_x)

view = dashboard_view(P, CFG)
c = view["cards"]

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Cost — $/m²", _fmt_usd(c["cost_per_m2"]))
with m2:
    st.metric("Revenue — $/m²", _fmt_usd(c["revenue_per_m2"]))
with m3:
    st.metric("Margin — $/m²", _fmt_usd(c["margin_per_m2"]),
              delta=f"{c['margin_pct']*100:.1f}%")
with m4:
    st.metric(f"Annual gross profit — {_stage_name}", f"${c['annual_gross_profit']:,.0f}",
              help="Margin/m² × annual good m² at the selected production scale.")

st.divider()

# -- Cost waterfall (per m²) -------------------------------------------------------
wf = view["waterfall"]
labels = [w[0] for w in wf]
vals = [w[1] for w in wf]
meas = [w[2] for w in wf]
texts = [f"${abs(v):,.2f}" for v in vals[:-1]] + [_fmt_usd(c["margin_per_m2"])]
tpos = ["outside"] * (len(wf) - 1) + ["inside"]
ec = "#1a7f37" if c["margin_per_m2"] >= 0 else "#b91c1c"

y_peak = max(c["revenue_per_m2"], c["cost_per_m2"])
y_floor = min(0.0, c["margin_per_m2"])
fig = go.Figure(go.Waterfall(
    orientation="v", measure=meas, x=labels, y=vals,
    text=texts, textposition=tpos,
    connector={"line": {"color": "#ccc", "dash": "dot"}},
    increasing={"marker": {"color": "#2d7d46"}},
    decreasing={"marker": {"color": "#c0392b"}},
    totals={"marker": {"color": ec}},
))
fig.update_layout(
    yaxis=dict(title=dict(text="USD / m²", font=dict(size=11), standoff=8),
               gridcolor="#eee", zeroline=True, zerolinecolor="#aaa",
               automargin=True, range=[y_floor * 1.15 - 1, y_peak * 1.2 + 1]),
    height=440, margin=dict(l=70, r=20, t=10, b=30),
    plot_bgcolor="white", paper_bgcolor="white", showlegend=False,
)
st.plotly_chart(fig, width="stretch")

# Per-bar formulas (hand-maintained to mirror engine/tea.py; per good m²).
WF_FORMULAS = {
    "Revenue": "Selling price ($/m²)",
    "Materials": "(coating loading (g/m²) × coating price ($/kg) ÷ 1000 + substrate $/m²) ÷ yield",
    "Labor": "FTEs × wage × (1 + burden) × paid h/yr ÷ good m²/yr × scale",
    "Energy": "(baseline kW × h/yr × elec price ÷ good m²/yr × scale) + (kWh/m² × elec price ÷ yield)",
    "Overhead": "fixed overhead ($/yr) ÷ good m²/yr × scale",
    "Disposal": "scrap mass (kg/m²) × disposal ($/kg) ÷ yield",
    "Margin": "Revenue − total cost",
}
with st.expander("How each bar is computed", expanded=False):
    st.caption("Fixed costs (labor, overhead, baseline energy) carry the production-scale "
               "factor; variable costs do not. That is why the fixed bars shrink as you raise "
               "the production scale and the variable floor stays put.")
    for lbl in labels:
        f = WF_FORMULAS.get(lbl)
        if f:
            st.markdown(f"**{lbl}** — {f}")


# -- Editor mode -------------------------------------------------------------------
# Open viewer app; the WRITE feature stays gated by a separate editor password (set only in
# the host's secrets manager). On the public open deploy no editor secret is set, so this
# stays a private feature -- viewer slider/scenario changes are always session-only.
st.divider()


def _editor_unlock():
    valid = _secret("editor_passwords")
    entered = st.session_state.get("ed_pwd_in", "")
    match = next((name for name, pw in valid.items() if entered and pw == entered), None)
    if match:
        st.session_state["editor"] = True
        st.session_state["editor_id"] = match
    else:
        st.session_state["editor_unlock_err"] = True


def _editor_lock():
    for k in ("editor", "editor_id", "staged_params", "staged_meta", "ed_scale_exponent"):
        st.session_state.pop(k, None)


with st.expander("🔒 Editor mode", expanded=st.session_state.get("editor", False)):
    if not st.session_state.get("editor"):
        st.caption("Demonstrates the authorized write path (validate → stage → save) we give "
                   "client teams. Viewer changes (sliders, scenarios) are session-only and "
                   "never written here.")
        st.text_input("Editor password", type="password", key="ed_pwd_in")
        st.button("Unlock editor", on_click=_editor_unlock)
        if st.session_state.pop("editor_unlock_err", False):
            st.error("Incorrect editor password (none is set on the public demo).")
    else:
        st.session_state.setdefault("staged_params", [])
        st.session_state.setdefault("staged_meta", [])
        pub = CFG["_meta"].get("publish", {})
        push_on = bool(pub.get("enabled"))

        head = st.columns([0.7, 0.3], vertical_alignment="center")
        head[0].success(f"Editor unlocked — id **{st.session_state['editor_id']}**")
        head[1].button("Lock", on_click=_editor_lock, width="stretch")

        st.markdown("##### Edit a parameter")
        sel = st.selectbox("Parameter", LEVER_KEYS,
                           format_func=lambda k: f"{PARAMS[k]['label']}  ({k})")
        m = PARAMS[sel]
        cur = {"value": m["value"], "min": m["slider"]["min"],
               "max": m["slider"]["max"], "step": m["slider"]["step"]}
        cc = st.columns(4)
        widgets = {
            "value": cc[0].number_input("default value", value=float(cur["value"]),
                                        key=f"ed_value_{sel}", format="%g"),
            "min": cc[1].number_input("slider min", value=float(cur["min"]),
                                      key=f"ed_min_{sel}", format="%g"),
            "max": cc[2].number_input("slider max", value=float(cur["max"]),
                                      key=f"ed_max_{sel}", format="%g"),
            "step": cc[3].number_input("slider step", value=float(cur["step"]),
                                       key=f"ed_step_{sel}", format="%g"),
        }
        if st.button("Stage parameter edit"):
            staged = [(sel, f, float(w)) for f, w in widgets.items()
                      if abs(float(w) - float(cur[f])) > 1e-12]
            keep = [(k, f, v) for (k, f, v) in st.session_state["staged_params"]
                    if not (k == sel and f in {f2 for (_, f2, _) in staged})]
            st.session_state["staged_params"] = keep + staged

        st.markdown("##### Pinned-default set")
        cur_pins = list(st.session_state.get("pinned", []))
        st.caption(f"Saved default: {PINNED_DEFAULT or '—'}  ·  your current pins: {cur_pins or '—'}")
        if st.button("Stage: set current pins as default"):
            st.session_state["staged_meta"] = [("pinned_default", cur_pins)]

        st.markdown("##### Scale model — exponent k")
        _cfg_k = float(CFG["_meta"].get("scale_stages", {}).get("exponent", 0.5))
        _k_opts = sorted({0.3, 0.4, 0.5, 0.6, 0.7, _cfg_k})
        st.session_state.setdefault("ed_scale_exponent", _cfg_k)
        kc1, kc2 = st.columns([0.7, 0.3], vertical_alignment="bottom")
        with kc1:
            st.selectbox("Production-scale exponent k  (fixed cost ∝ capacity^(k−1))", _k_opts,
                         key="ed_scale_exponent",
                         help="Lower k = stronger scale economies. Live-previews on the "
                              "Production-scale selector; 'Save k' persists it.")
        _k_dirty = abs(float(st.session_state["ed_scale_exponent"]) - _cfg_k) > 1e-12
        with kc2:
            if st.button("Save k", disabled=not _k_dirty, width="stretch"):
                res = save_and_publish(
                    [], [], editor=st.session_state["editor_id"], reason="scale exponent",
                    config_path=CONFIG_PATH, remote=pub.get("remote", "origin"),
                    branch=pub.get("branch"), push=push_on,
                    exponent=float(st.session_state["ed_scale_exponent"]))
                if res["saved"]:
                    st.success(f"Saved k={st.session_state['ed_scale_exponent']:g}"
                               f"{' & pushed' if res['pushed'] else ''}.")
                    st.rerun()
                else:
                    st.error("Rejected: " + "; ".join(res["problems"]))

        st.markdown("##### Staged changes")
        sp, sm = st.session_state["staged_params"], st.session_state["staged_meta"]
        if not sp and not sm:
            st.caption("_Nothing staged._")
        else:
            for (k, f, v) in sp:
                st.write(f"• `{k}` · {f} → {v:g}")
            for (mk, keys) in sm:
                st.write(f"• `_meta.{mk}` → {keys}")
            st.button("Clear staged",
                      on_click=lambda: st.session_state.update(staged_params=[], staged_meta=[]))

        reason = st.text_input("Reason (logged with each edit)", key="ed_reason")
        tgt = f"{pub.get('remote', 'origin')}/{pub.get('branch')}"
        st.caption(f"Publish: {'ON → push to ' + tgt if push_on else 'OFF — saves to config file only'}")
        if st.button("💾 Save" + (" & publish" if push_on else ""),
                     type="primary", disabled=not (sp or sm)):
            res = save_and_publish(
                list(sp), list(sm), editor=st.session_state["editor_id"], reason=reason,
                config_path=CONFIG_PATH, remote=pub.get("remote", "origin"),
                branch=pub.get("branch"), push=push_on)
            if not res["saved"]:
                st.error("Rejected — config untouched: " + "; ".join(res["problems"]))
            else:
                st.session_state["staged_params"] = []
                st.session_state["staged_meta"] = []
                if res["pushed"]:
                    st.success(f"Saved & pushed {len(res['entries'])} edit(s). {res['detail']}")
                elif push_on:
                    st.warning(f"Saved to config, but push failed: {res['detail']}")
                else:
                    st.info(f"Saved {len(res['entries'])} edit(s) to config (push off).")
                st.rerun()
