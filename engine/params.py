"""Parameter loader for the Demo Co. R2R membrane TEA (illustrative).

The config file `config/params.json` is the single source of truth for every
parameter's value and UI metadata (slider endpoints/step, status, category,
influence tier, source, change log). This module loads it and exposes:

    P = load_params()          # dict: key -> value  (what the engine math uses)
    META = load_meta()         # full per-param metadata (what the UI/edit-mode uses)

Keeping the math (value only) separate from the metadata keeps the engine
UI-free. The passworded edit-mode writes back to the same JSON and appends
change_log entries; nothing here hardcodes a number.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "params.json"


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_params(path=CONFIG_PATH):
    """Flat dict of key -> current value, for the engine math."""
    cfg = load_config(path)
    return {k: v["value"] for k, v in cfg["params"].items()}


def load_meta(path=CONFIG_PATH):
    """Full per-param metadata, for the UI / edit-mode."""
    return load_config(path)["params"]


def print_table(path=CONFIG_PATH):
    cfg = load_config(path)
    params = cfg["params"]
    # group by category, preserving first-seen order
    cats = []
    for meta in params.values():
        if meta["category"] not in cats:
            cats.append(meta["category"])

    hdr = f"{'parameter':<26} {'value':>10}  {'unit':<10} {'status':<15} {'tier':<11} {'slider [min, max, step]'}"
    print(hdr)
    print("-" * len(hdr))
    for cat in cats:
        print(f"\n[{cat}]")
        for key, m in params.items():
            if m["category"] != cat:
                continue
            s = m["slider"]
            srange = "-" if s is None else f"[{s['min']}, {s['max']}, {s['step']}]"
            print(f"{m['label']:<26} {str(m['value']):>10}  {m['unit']:<10} "
                  f"{m['status']:<15} {m['tier']:<11} {srange}")

    n = len(params)
    n_slider = sum(1 for m in params.values() if m["slider"] is not None)
    tiers = {}
    for m in params.values():
        tiers[m["tier"]] = tiers.get(m["tier"], 0) + 1
    print(f"\n{n} params total | {n_slider} sliders | tier counts: {tiers}")


if __name__ == "__main__":
    print_table()
