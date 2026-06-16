"""Audit gate 11 (editor-mode meta + publish integrity).

Extends gate 5 (param write-back) to the rest of the editor Save path:

  A. update_meta round-trips: set pinned_default -> reload -> identical list, _meta change_log
     +1; a non-editable target and an unknown key are BOTH refused without touching the file.
  B. apply_staged is all-or-nothing + sanity-gated: a valid batch (param + meta edit) promotes
     and appends both change_logs; an out-of-range edit is refused leaving the file byte-
     identical; sanity_ok rejects a config that yields a non-finite headline.
  C. git_publish works end-to-end against a TEMP repo + bare remote (never the real remote):
     a real change commits + pushes; no change reports "nothing to commit".

All of A/B run on a temp COPY of the real config; C runs in its own temp git repo. Exit 0 iff
all hold (used by audit/run_gates.py).
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEA = Path(__file__).resolve().parent
sys.path.insert(0, str(TEA / "engine"))
from params import load_config                       # noqa: E402
from edit_mode import update_param, update_meta, update_scale_exponent   # noqa: E402
from publish import apply_staged, sanity_ok, git_publish   # noqa: E402

REAL_CFG = TEA / "config" / "params.json"
KEY = "coat_material_price"


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def check_meta(tmp, problems):
    cfg0 = load_config(tmp)
    base_keys = list(cfg0["_meta"]["pinned_default"]["keys"])
    log0 = len(cfg0["_meta"].get("change_log", []))
    new_keys = list(reversed(base_keys))             # same keys, new order

    update_meta("pinned_default", new_keys, editor="gate11", reason="meta round-trip", path=tmp)
    cfg1 = load_config(tmp)
    if cfg1["_meta"]["pinned_default"]["keys"] != new_keys:
        problems.append("update_meta did not persist the new pinned_default list")
    if len(cfg1["_meta"].get("change_log", [])) != log0 + 1:
        problems.append("update_meta did not append a _meta change_log entry")

    before = tmp.read_text(encoding="utf-8")
    for label, call in [
        ("non-editable target", lambda: update_meta("minor_factors", base_keys, path=tmp)),
        ("unknown key", lambda: update_meta("pinned_default", ["not_a_real_param"], path=tmp)),
    ]:
        try:
            call()
            problems.append(f"update_meta accepted a bad edit ({label})")
        except (ValueError, KeyError, TypeError):
            pass
    if tmp.read_text(encoding="utf-8") != before:
        problems.append("a refused update_meta still modified the file")

    # update_scale_exponent: a valid k persists; out-of-range / non-numeric refused, file intact
    update_scale_exponent(0.6, editor="gate11", reason="exp round-trip", path=tmp)
    if abs(load_config(tmp)["_meta"]["scale_stages"]["exponent"] - 0.6) > 1e-12:
        problems.append("update_scale_exponent did not persist a valid k")
    before_k = tmp.read_text(encoding="utf-8")
    for bad in (1.5, 0.0, "x"):
        try:
            update_scale_exponent(bad, path=tmp)
            problems.append(f"update_scale_exponent accepted a bad k ({bad!r})")
        except (ValueError, TypeError):
            pass
    if tmp.read_text(encoding="utf-8") != before_k:
        problems.append("a refused update_scale_exponent still modified the file")


def check_apply_and_sanity(tmp, problems):
    cfg = load_config(tmp)
    cm0 = cfg["params"][KEY]["value"]
    cm_log0 = len(cfg["params"][KEY]["change_log"])
    meta_log0 = len(cfg["_meta"].get("change_log", []))
    pin0 = list(cfg["_meta"]["pinned_default"]["keys"])

    # valid batch: a param edit + a meta edit -> promoted, both logs +1
    ok, probs, entries = apply_staged(
        [(KEY, "value", cm0 + 10)],
        [("pinned_default", list(reversed(pin0)))],
        editor="gate11", reason="apply_staged ok", path=tmp)
    cfg1 = load_config(tmp)
    if not ok:
        problems.append(f"apply_staged rejected a valid batch: {probs}")
    if abs(cfg1["params"][KEY]["value"] - (cm0 + 10)) > 1e-9:
        problems.append("apply_staged did not persist the param edit")
    if len(cfg1["params"][KEY]["change_log"]) != cm_log0 + 1:
        problems.append("apply_staged did not append the param change_log")
    if len(cfg1["_meta"].get("change_log", [])) != meta_log0 + 1:
        problems.append("apply_staged did not append the _meta change_log")

    # out-of-range edit refused, file byte-identical
    before = tmp.read_text(encoding="utf-8")
    hi = cfg1["params"][KEY]["slider"]["max"]
    ok2, probs2, _ = apply_staged([(KEY, "value", hi + 1000)], [],
                                  editor="gate11", path=tmp)
    if ok2:
        problems.append("apply_staged accepted an out-of-range edit")
    if tmp.read_text(encoding="utf-8") != before:
        problems.append("a refused apply_staged still modified the file")

    # sanity_ok: clean config passes; zero-yield config (non-finite headline) fails
    ok_clean, _ = sanity_ok(cfg1)
    if not ok_clean:
        problems.append("sanity_ok failed on a clean config")
    bad = load_config(tmp)
    bad["params"]["oee_quality"]["value"] = 0
    ok_bad, bad_probs = sanity_ok(bad)
    if ok_bad:
        problems.append("sanity_ok passed a config with a non-finite headline")


def check_git(problems):
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "work"
        bare = Path(td) / "remote.git"
        repo.mkdir()
        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "gate11@test"], repo)
        _git(["config", "user.name", "gate11"], repo)
        cfgfile = repo / "params.json"
        cfgfile.write_text('{"v": 1}\n', encoding="utf-8")
        _git(["add", "-A"], repo)
        _git(["commit", "-m", "init"], repo)
        _git(["init", "--bare", str(bare)], td)
        _git(["remote", "add", "origin", str(bare)], repo)
        _git(["push", "-u", "origin", "main"], repo)

        # a real change -> commit + push
        cfgfile.write_text('{"v": 2}\n', encoding="utf-8")
        ok, detail = git_publish("gate11 change", [cfgfile], remote="origin",
                                 branch="main", cwd=repo)
        if not ok:
            problems.append(f"git_publish failed on a real change: {detail}")
        remote_head = _git(["rev-parse", "origin/main"], repo).stdout.strip()
        local_head = _git(["rev-parse", "HEAD"], repo).stdout.strip()
        if remote_head != local_head:
            problems.append("git_publish did not advance the remote to the new commit")

        # no change -> reported, not an error
        ok2, detail2 = git_publish("gate11 noop", [cfgfile], remote="origin",
                                   branch="main", cwd=repo)
        if not (ok2 and "nothing to commit" in detail2.lower() or "no change" in detail2.lower()):
            problems.append(f"git_publish on no change not handled cleanly: {detail2}")


def check_bounds(tmp, problems):
    """The editor cannot enter nonsense ranges: step wider than the range, a negative min, or a
    fraction max above 1 are all refused without touching the file; a valid tightening is kept."""
    before = tmp.read_text(encoding="utf-8")
    nonsense = [
        ("coat_loading", "min", -5, "negative min"),
        ("coat_loading", "step", 1000, "step wider than range"),
        ("oee_quality", "max", 1.5, "fraction max > 1"),
    ]
    for key, field, val, label in nonsense:
        try:
            update_param(key, field, val, editor="gate11", reason="bounds neg-test", path=tmp)
            problems.append(f"bounds: accepted {label} ({key}.{field}={val})")
        except (ValueError, KeyError):
            pass
    if tmp.read_text(encoding="utf-8") != before:
        problems.append("bounds: a refused edit still modified the file")
    try:
        update_param("coat_loading", "min", 10, editor="gate11",
                     reason="valid tighten", path=tmp)
    except Exception as e:                            # noqa: BLE001
        problems.append(f"bounds: rejected a valid edit (coat_loading.min=10): {e}")


def main():
    problems = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "params.json"
        shutil.copy(REAL_CFG, tmp)
        check_meta(tmp, problems)
        check_apply_and_sanity(tmp, problems)
        check_bounds(tmp, problems)
    check_git(problems)

    print("=" * 60)
    print("AUDIT GATE 11 -- editor meta + publish integrity")
    print("=" * 60)
    if problems:
        print(f"  PROBLEMS ({len(problems)}):")
        for pr in problems:
            print(f"    - {pr}")
    else:
        print("  PASS -- update_meta round-trips, apply_staged is sanity-gated &")
        print("          all-or-nothing, git_publish commits+pushes to a temp remote")
    return not problems


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
