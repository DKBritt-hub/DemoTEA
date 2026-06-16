"""Editor-mode save path: the guards that let an authorized editor persist config
changes durably AND safely. The Streamlit Save button calls `save_and_publish`, which is:

  1. apply_staged  -- apply all staged edits to a TEMP copy via update_param/update_meta
                      (each re-validates the provenance invariants), require the resulting
                      config to pass sanity_ok, and only then atomically promote the temp over
                      the real file. All-or-nothing: a bad invariant OR a non-finite headline
                      aborts with the real config untouched.
  2. git_publish   -- stage ONLY the config file(s) handed in, commit, and push to the
                      configured remote/branch. The app never commits arbitrary paths.

sanity_ok is the "always-runnable defaults" guard: an editor can make the numbers silly, but
cannot push a config that crashes the model or yields inf/nan for the next viewer.

Durability / credentials: this runs where git push is authenticated -- the editor's local
clone (or a host that owns a repo-scoped deploy token). The public viewer deployment has no
push creds and never reaches git_publish; that absence IS the security boundary.
"""

import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from params import CONFIG_PATH, load_config        # noqa: E402
from model import default_params, run_model          # noqa: E402
from edit_mode import update_param, update_meta, update_scale_exponent   # noqa: E402

TEA_DIR = Path(__file__).resolve().parent.parent      # engine/ -> tea/


def sanity_ok(cfg):
    """Run the engine at the deliverable opening basis and require every headline number to be
    finite. Returns (ok, problems). A raised engine exception or any inf/nan headline fails it.
    """
    try:
        P = default_params(cfg)
        r = run_model(P, cfg)
    except Exception as e:                            # noqa: BLE001 - any engine failure = unsafe
        return False, [f"engine raised on the edited config: {e}"]
    headline = {
        "cost_per_m2": r["full"]["total_m2"],
        "revenue_per_m2": r["value"]["revenue_per_m2"],
        "margin_per_m2": r["value"]["margin_per_m2"],
        "annual_gross_profit": r["value"]["annual_gross_profit"],
    }
    problems = [f"{name} is not finite ({v})"
                for name, v in headline.items()
                if v is None or not math.isfinite(v)]
    return (not problems), problems


def apply_staged(param_edits, meta_edits, editor="unknown", reason="", path=CONFIG_PATH,
                 exponent=None):
    """Apply staged edits all-or-nothing.

    param_edits: iterable of (key, field, new_value)   (field in value/min/max/step)
    meta_edits:  iterable of (meta_key, new_keys)        (e.g. ("pinned_default", [...]))

    Applies every edit to a temp copy of `path` (reusing update_param/update_meta so the
    invariant checks + change_log are identical to any other write), requires sanity_ok on the
    result, then atomically promotes the temp over the real file. On any failure the real file
    is left exactly as it was. Returns (ok, problems, entries).
    """
    path = Path(path)
    fd, tmpname = tempfile.mkstemp(suffix=".json", dir=str(path.parent))
    os.close(fd)
    tmp = Path(tmpname)
    entries = []
    try:
        shutil.copy(path, tmp)
        for key, field, val in param_edits:
            entries.append(update_param(key, field, val, editor=editor,
                                        reason=reason, path=tmp))
        for meta_key, new_keys in meta_edits:
            entries.append(update_meta(meta_key, new_keys, editor=editor,
                                       reason=reason, path=tmp))
        if exponent is not None:
            entries.append(update_scale_exponent(exponent, editor=editor,
                                                  reason=reason, path=tmp))
        ok, problems = sanity_ok(load_config(tmp))
        if not ok:
            return False, problems, []
        os.replace(tmp, path)                         # atomic promote (same filesystem)
        return True, [], entries
    except (ValueError, KeyError, TypeError) as e:    # invariant / unknown-key / type rejection
        return False, [str(e)], []
    finally:
        if tmp.exists():
            tmp.unlink()


def git_publish(message, files, remote="origin", branch=None, cwd=None):
    """Stage exactly `files`, commit with `message`, and push. Returns (ok, detail).

    Only the paths in `files` are ever staged -- the app hands in just the config file, so no
    arbitrary content can be pushed through this. `cwd` defaults to the tea/ dir; git resolves
    the enclosing repo from there. A failed push after a successful commit is reported (the
    commit is local and recoverable from the CLI).
    """
    cwd = str(cwd or TEA_DIR)
    try:
        for f in files:
            r = subprocess.run(["git", "add", "--", str(f)], cwd=cwd,
                               capture_output=True, text=True)
            if r.returncode != 0:
                return False, f"git add failed: {r.stderr.strip() or r.stdout.strip()}"
        commit = subprocess.run(["git", "commit", "-m", message], cwd=cwd,
                                capture_output=True, text=True)
        if commit.returncode != 0:
            blob = (commit.stdout + commit.stderr).lower()
            if "nothing to commit" in blob:
                return True, "no change to commit"
            return False, f"git commit failed: {commit.stderr.strip() or commit.stdout.strip()}"
        push_cmd = ["git", "push", remote] + ([branch] if branch else [])
        push = subprocess.run(push_cmd, cwd=cwd, capture_output=True, text=True)
        if push.returncode != 0:
            return False, ("committed locally but PUSH FAILED (recover/retry from CLI): "
                           + (push.stderr.strip() or push.stdout.strip()))
        return True, "committed and pushed"
    except FileNotFoundError:
        return False, "git not found on PATH"


def save_and_publish(param_edits, meta_edits, editor="unknown", reason="",
                     config_path=CONFIG_PATH, remote="origin", branch=None, cwd=None,
                     push=True, exponent=None):
    """Full editor Save: apply staged edits (sanity-gated, atomic) then, if `push`, git commit
    + push. With push=False the edits persist to the config file but nothing touches git -- the
    safe default until a real deploy repo is wired (so a local spin can't push test commits).
    `exponent` (when not None) also persists _meta.scale_stages.exponent.

    Returns {saved, pushed, detail, problems, entries}. If the sanity/invariant guard rejects
    the edits, nothing is written and nothing is pushed.
    """
    ok, problems, entries = apply_staged(param_edits, meta_edits, editor=editor,
                                         reason=reason, path=config_path, exponent=exponent)
    if not ok:
        return {"saved": False, "pushed": False, "detail": "edits rejected before write",
                "problems": problems, "entries": []}
    if not push:
        return {"saved": True, "pushed": False, "detail": "saved to config; push disabled",
                "problems": [], "entries": entries}
    msg = message_for(entries, editor)
    pushed, detail = git_publish(msg, files=[config_path], remote=remote,
                                 branch=branch, cwd=cwd)
    return {"saved": True, "pushed": pushed, "detail": detail,
            "problems": [], "entries": entries}


def message_for(entries, editor):
    """One-line commit message summarizing the saved edits."""
    n = len(entries)
    return f"Editor save ({editor}): {n} config edit{'s' if n != 1 else ''}"
