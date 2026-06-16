"""Edit-mode write-back: the only sanctioned path that mutates
config/params.json, with a change-log entry per edit and integrity guards.

The deliverable's edit mode is a passworded surface that lets an authorized editor adjust
a slider's endpoints/step or a param's default value and have it persist to the single
source of truth. The risk is corrupting that source of truth, so every write goes through
`update_param`, which:

  - accepts only the four editable fields (value, min, max, step);
  - validates the resulting param still satisfies the provenance invariants
    (min < max, step > 0, min <= value <= max) BEFORE writing -- a rejected edit leaves
    the file untouched;
  - appends a change_log entry {ts, editor, field, old, new, reason};
  - writes atomically (temp file + replace) so an interrupted write can't truncate config.

The round-trip guarantee (write -> reload -> identical engine result, log appended) is
proven by round_trip_check.py (audit gate 5). The Streamlit edit-mode forms and the
agentic update hooks call THIS function -- they never write JSON directly.
"""

import json
import math
from datetime import datetime
from pathlib import Path

from params import CONFIG_PATH, load_config   # noqa: E402

EDITABLE_FIELDS = {"value", "min", "max", "step"}   # min/max/step live under "slider"


def bounds(p):
    """Hard editor bounds for one param's slider: (hard_min, hard_max). Defaults keep an editor
    from entering nonsense without per-param domain tables: floor at 0 (every model input is a
    non-negative quantity) and cap `fraction`-unit params at 1.0 (their physical ceiling);
    everything else is unbounded above. Both are overridable per-param via slider.hard_min /
    slider.hard_max (e.g. a param that may legitimately go negative, or a fraction-as-multiplier
    that may exceed 1)."""
    sl = p.get("slider") or {}
    hard_min = sl.get("hard_min", 0.0)
    hard_max = sl["hard_max"] if "hard_max" in sl else (
        1.0 if p.get("unit") == "fraction" else math.inf)
    return hard_min, hard_max


def _validate(p):
    """Provenance + sanity invariants that must hold after an edit, else we refuse to write.
    Beyond the structural checks, an editor cannot set a step wider than the range, a min below
    the allowed floor, or a max above the allowed ceiling (see `bounds`)."""
    sl = p.get("slider")
    v = p.get("value")
    if isinstance(sl, dict):
        lo, hi, step = sl.get("min"), sl.get("max"), sl.get("step")
        if lo is None or hi is None or step is None:
            return "slider missing min/max/step"
        if not lo < hi:
            return f"min {lo} not < max {hi}"
        if step <= 0:
            return f"step {step} not > 0"
        if step > hi - lo:
            return f"step {step:g} exceeds the slider range {hi - lo:g} (max - min)"
        hard_min, hard_max = bounds(p)
        if lo < hard_min:
            return f"min {lo:g} below the allowed floor {hard_min:g}"
        if hi > hard_max:
            return f"max {hi:g} above the allowed ceiling {hard_max:g}"
        if v is None or not lo <= v <= hi:
            return f"value {v} outside [{lo}, {hi}]"
    return None


def _atomic_write(cfg, path):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def update_param(key, field, new_value, editor="unknown", reason="", path=CONFIG_PATH):
    """Write one editable field of one param, log it, and persist atomically.

    Returns the change_log entry. Raises (without writing) on an unknown key/field or an
    edit that would violate the provenance invariants.
    """
    if field not in EDITABLE_FIELDS:
        raise ValueError(f"field {field!r} not editable; allowed {sorted(EDITABLE_FIELDS)}")
    cfg = load_config(path)
    if key not in cfg["params"]:
        raise KeyError(f"unknown param {key!r}")
    p = cfg["params"][key]

    if field == "value":
        old = p.get("value")
        p["value"] = new_value
    else:  # min/max/step under slider
        if not isinstance(p.get("slider"), dict):
            raise ValueError(f"param {key!r} has no slider to edit {field!r}")
        old = p["slider"].get(field)
        p["slider"][field] = new_value

    err = _validate(p)
    if err:
        raise ValueError(f"edit rejected ({key}.{field}={new_value}): {err}")

    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "editor": editor, "field": field, "old": old, "new": new_value,
        "reason": reason,
    }
    p.setdefault("change_log", []).append(entry)
    _atomic_write(cfg, path)
    return entry


META_EDITABLE = {"pinned_default"}   # _meta buckets whose `keys` list an editor may set


def update_meta(meta_key, new_keys, editor="unknown", reason="", path=CONFIG_PATH):
    """Set the `keys` list of one editable _meta bucket (e.g. pinned_default), log it under
    _meta.change_log, and persist atomically. Same discipline as update_param: validate
    BEFORE writing, and reject (leaving the file untouched) on a bad target or bad key list.

    `new_keys` must be a list of DISTINCT param keys that exist in config.params. The UI only
    ever offers lever keys, but the engine guards independently. Returns the change_log entry.
    """
    if meta_key not in META_EDITABLE:
        raise ValueError(f"_meta {meta_key!r} not editable; allowed {sorted(META_EDITABLE)}")
    if not isinstance(new_keys, (list, tuple)):
        raise TypeError(f"new_keys must be a list, got {type(new_keys).__name__}")
    keys = list(new_keys)
    if len(set(keys)) != len(keys):
        raise ValueError("new_keys contains duplicate keys")
    cfg = load_config(path)
    unknown = [k for k in keys if k not in cfg["params"]]
    if unknown:
        raise KeyError(f"unknown param key(s) in new_keys: {unknown}")

    bucket = cfg["_meta"].setdefault(meta_key, {})
    old = list(bucket.get("keys", []))
    bucket["keys"] = keys

    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "editor": editor, "target": f"_meta.{meta_key}.keys",
        "old": old, "new": keys, "reason": reason,
    }
    cfg["_meta"].setdefault("change_log", []).append(entry)
    _atomic_write(cfg, path)
    return entry


def update_scale_exponent(value, editor="unknown", reason="", path=CONFIG_PATH):
    """Set _meta.scale_stages.exponent (the production-scale fixed-cost dilution exponent k),
    log under _meta.change_log, persist atomically. Validate before writing: k in [0.1, 1.0].
    This is the edit-mode-only knob behind the public Production-scale selector (no public
    control). Same discipline as update_param/update_meta: reject (file untouched) if invalid."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("scale exponent must be a number")
    if not 0.1 <= value <= 1.0:
        raise ValueError(f"scale exponent {value} outside [0.1, 1.0]")
    cfg = load_config(path)
    ss = cfg["_meta"].setdefault("scale_stages", {})
    old = ss.get("exponent")
    ss["exponent"] = float(value)
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "editor": editor, "target": "_meta.scale_stages.exponent",
        "old": old, "new": float(value), "reason": reason,
    }
    cfg["_meta"].setdefault("change_log", []).append(entry)
    _atomic_write(cfg, path)
    return entry
