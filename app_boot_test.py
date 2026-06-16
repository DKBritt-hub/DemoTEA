"""Headless boot test for streamlit_app.py (dev smoke test, not a gate).

Uses streamlit.testing.v1.AppTest to actually execute the app body -- slider generation
from config, dashboard_view -> engine, plotly waterfall -- without a browser. Bypasses
the password gate via session_state. Confirms the app renders with no exception and that
the generated sliders match the config's lever count. Kept out of run_gates.py so the
gate suite stays dependency-light (engine only)."""

from pathlib import Path
from streamlit.testing.v1 import AppTest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from params import load_config   # noqa: E402


def main():
    cfg = load_config()
    hidden = set(cfg["_meta"].get("hidden_factors", {}).get("keys", []))
    levers = [k for k, m in cfg["params"].items()
              if m.get("status") != "constant"
              and m.get("tier") not in ("fixed", "negligible")
              and isinstance(m.get("slider"), dict)
              and k not in hidden]
    pinned = [k for k in cfg["_meta"].get("pinned_default", {}).get("keys", [])
              if k in levers]
    # each lever renders a group twin; pinned levers render a second (mirror) twin up top
    expected_sliders = len(levers) + len(pinned)

    at = AppTest.from_file(str(Path(__file__).resolve().parent / "streamlit_app.py"),
                           default_timeout=30)
    at.session_state["authenticated"] = True
    at.run()

    print("=" * 56)
    print("STREAMLIT APP BOOT TEST")
    print("=" * 56)
    if at.exception:
        print(f"  EXCEPTION: {at.exception}")
        return False
    n_sliders = len(at.slider)
    n_metrics = len(at.metric)
    keys = {s.key for s in at.slider}
    print(f"  rendered with no exception")
    print(f"  sliders rendered: {n_sliders}  (expected {expected_sliders} = "
          f"{len(levers)} group + {len(pinned)} pinned mirrors)")
    print(f"  metric cards: {n_metrics}")
    counts_ok = (n_sliders == expected_sliders) and (n_metrics == 4)

    # mirror present + in sync: a pinned param has BOTH twins; moving the top moves the group
    sync_ok = True
    if pinned:
        k = pinned[0]
        both = f"{k}__top" in keys and f"{k}__grp" in keys
        if not both:
            sync_ok = False
            print(f"  mirror: {k} missing a twin (top in keys: {f'{k}__top' in keys}, "
                  f"grp in keys: {f'{k}__grp' in keys})")
        else:
            top = next(s for s in at.slider if s.key == f"{k}__top")
            target = top.value + top.step
            top.set_value(target).run()
            grp_val = at.session_state[f"{k}__grp"]
            v_val = at.session_state[f"v_{k}"]
            sync_ok = abs(grp_val - target) < 1e-9 and abs(v_val - target) < 1e-9 \
                and not at.exception
            print(f"  mirror sync: set {k}__top={target} -> grp={grp_val}, v={v_val}  "
                  f"{'OK' if sync_ok else 'MISMATCH'}")

    # pin preserves value: move a non-pinned group slider, pin it, confirm value survives
    preserve_ok = True
    nonpinned = [k for k in levers if k not in pinned]
    if nonpinned:
        k = nonpinned[0]
        grp = next((s for s in at.slider if s.key == f"{k}__grp"), None)
        if grp is None:
            preserve_ok = False
            print(f"  pin-preserve: could not find {k}__grp slider")
        else:
            target = grp.value + grp.step
            grp.set_value(target).run()
            next(b for b in at.button if b.key == f"tack_grp_{k}").click().run()
            kept = at.session_state[f"v_{k}"]
            preserve_ok = abs(kept - target) < 1e-9 and not at.exception
            print(f"  pin-preserves-value: set {k}={target}, pinned -> v_{k}={kept}  "
                  f"{'OK' if preserve_ok else 'RESET'}")

    # editor-mode UNLOCKED branch renders without exception (the write logic itself is proven
    # on a temp config by gate 11; here we only confirm the unlocked UI renders its widgets).
    ate = AppTest.from_file(str(Path(__file__).resolve().parent / "streamlit_app.py"),
                            default_timeout=30)
    ate.session_state["authenticated"] = True
    ate.session_state["editor"] = True
    ate.session_state["editor_id"] = "smoke"
    ate.run()
    editor_ok = (not ate.exception) and len(ate.selectbox) >= 1 and len(ate.number_input) >= 4
    print(f"  editor unlocked: exception={bool(ate.exception)}, "
          f"selectbox={len(ate.selectbox)}, number_inputs={len(ate.number_input)}  "
          f"{'OK' if editor_ok else 'FAIL'}")

    ok = counts_ok and sync_ok and preserve_ok and editor_ok
    print(f"  {'PASS' if ok else 'FAIL'} -- "
          f"{'mirror in sync + value preserved + editor renders' if ok else 'check failed above'}")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
