"""Audit gate runner (audit structure gate 1: regression).

Runs every acceptance/regression gate as a child process and reports one green/red.
Exit 0 iff all gates pass. Run this before every commit that touches the engine,
config, or check scripts -- a new cost line silently breaking closure or the regression
anchor is the most likely failure mode as the model grows.

Each gate owns its pass/fail via process exit code (no output parsing), so a gate
that crashes counts as RED rather than silently passing.

  engine/run.py            -- regression vs synthetic pilot anchor
  validate_massbalance.py  -- mass-balance intermediates, row-level
  streams.py               -- closed solids balance (coating+substrate == product+scrap)
  layer_check.py           -- layer-boundary reconciliation
  ui_parity_check.py       -- dashboard renders engine output exactly
  round_trip_check.py      -- edit-mode write-back integrity / round-trip
  meta_publish_check.py    -- editor meta (update_meta) + save/sanity/git publish
  consistency_check.py     -- identities + couplings + plausibility; latent-stub catcher
  bounds_finite_check.py   -- every lever min/max yields a finite headline (no singularity)
  perturbation.py          -- response-class oracle (exact scaling + sign)
  scale_check.py           -- per-m2 variable invariance; fixed dilutes; throughput scales
  audit/provenance_check.py -- params.json provenance / slider integrity
"""

import subprocess
import sys
from pathlib import Path

TEA = Path(__file__).resolve().parent.parent  # .../tea

GATES = [
    ("Regression (synthetic anchor)", "engine/run.py"),
    ("Mass-balance rows", "validate_massbalance.py"),
    ("Closed mass balance", "streams.py"),
    ("Layer reconciliation", "layer_check.py"),
    ("UI-engine parity", "ui_parity_check.py"),
    ("Edit-mode round-trip", "round_trip_check.py"),
    ("Editor meta + publish", "meta_publish_check.py"),
    ("Physical consistency", "consistency_check.py"),
    ("Bounds finite (no singularity)", "bounds_finite_check.py"),
    ("Perturbation oracle", "perturbation.py"),
    ("Scale invariance", "scale_check.py"),
    ("Param provenance", "audit/provenance_check.py"),
]


def main():
    results = []
    for name, rel in GATES:
        p = subprocess.run([sys.executable, str(TEA / rel)],
                           cwd=str(TEA), capture_output=True, text=True)
        results.append((name, rel, p.returncode, p.stderr.strip()))

    width = max(len(n) for n, *_ in results)
    print("=" * (width + 34))
    print("DEMO CO. MEMBRANE TEA -- AUDIT GATES")
    print("=" * (width + 34))
    n_pass = 0
    for name, rel, rc, err in results:
        ok = rc == 0
        n_pass += ok
        verdict = "PASS" if ok else f"FAIL (exit {rc})"
        print(f"  {name:<{width}}  {rel:<26}  {verdict}")
        if not ok and err:
            tail = err.splitlines()[-1] if err.splitlines() else err
            print(f"  {'':<{width}}  {'':<26}  ! {tail}")
    print("-" * (width + 34))
    allok = n_pass == len(results)
    print(f"  {n_pass}/{len(results)} gates passed  ->  {'ALL GREEN' if allok else 'RED'}")
    return allok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
