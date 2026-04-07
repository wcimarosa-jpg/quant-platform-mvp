#!/usr/bin/env python3
"""Golden dataset generator.

Runs each analysis methodology against the deterministic synthetic data
(seed=42, n=200) and saves expected outputs as JSON. These golden files
are the reference for regression tests.

Usage:
    python -m data.fixtures.golden.generator

Workflow for updating golden datasets:
1. Make the code change that legitimately alters output
2. Run this script to regenerate expected outputs
3. Run regression tests to confirm they now pass
4. Commit both the code change and updated golden files together
5. Include a note in the PR explaining why the golden output changed
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure imports work from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Import analyses to trigger registration
import packages.survey_analysis.drivers  # noqa: F401
import packages.survey_analysis.segmentation  # noqa: F401
import packages.survey_analysis.maxdiff_turf  # noqa: F401

from data.fixtures.small.p07_synthetic import (
    dv_columns,
    iv_columns,
    make_survey_df,
    maxdiff_items,
    turf_acceptance_columns,
)
from packages.survey_analysis.run_orchestrator import (
    AnalysisRun,
    RunConfig,
    RunVersions,
    execute_run,
)

GOLDEN_DIR = Path(__file__).resolve().parent
SEED = 42
N = 200


def _versions() -> RunVersions:
    return RunVersions(
        questionnaire_id="qre-golden",
        questionnaire_version=1,
        mapping_id="map-golden",
        mapping_version=1,
        data_file_hash="sha256:golden-fixture",
    )


def _save(name: str, data: dict) -> Path:
    path = GOLDEN_DIR / f"{name}_expected.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Saved: {path.name} ({len(json.dumps(data))} bytes)")
    return path


def generate_all() -> dict[str, str]:
    """Generate all golden datasets. Returns {name: status}."""
    df = make_survey_df(n=N, seed=SEED)
    versions = _versions()
    results = {}

    # Drivers
    run = AnalysisRun(project_id="golden", config=RunConfig(analysis_type="drivers"), versions=versions)
    result = execute_run(run, df=df, iv_cols=iv_columns(), dv_cols=dv_columns())
    if result.status.value == "completed":
        _save("drivers", result.result_summary)
        results["drivers"] = "ok"
    else:
        results["drivers"] = f"FAILED: {result.error_message}"

    # MaxDiff/TURF
    run = AnalysisRun(project_id="golden", config=RunConfig(analysis_type="maxdiff_turf"), versions=versions)
    result = execute_run(run, df=df, maxdiff_columns=maxdiff_items(), acceptance_columns=turf_acceptance_columns())
    if result.status.value == "completed":
        _save("maxdiff_turf", result.result_summary)
        results["maxdiff_turf"] = "ok"
    else:
        results["maxdiff_turf"] = f"FAILED: {result.error_message}"

    # Segmentation
    run = AnalysisRun(project_id="golden", config=RunConfig(analysis_type="segmentation"), versions=versions)
    result = execute_run(run, df=df, clustering_vars=iv_columns())
    if result.status.value == "completed":
        _save("segmentation", result.result_summary)
        results["segmentation"] = "ok"
    else:
        results["segmentation"] = f"FAILED: {result.error_message}"

    return results


if __name__ == "__main__":
    print(f"Generating golden datasets (seed={SEED}, n={N})")
    results = generate_all()
    print()
    for name, status in results.items():
        print(f"  {name}: {status}")
    if all(v == "ok" for v in results.values()):
        print("\nAll golden datasets generated successfully.")
    else:
        print("\nSome datasets FAILED. Check errors above.")
        sys.exit(1)
