"""Read-only local performance measurements for the Seranews demo.

This script reads the supplied ZIP and the prepared catalog. It does not call
paid services or write to the catalog, original article database, or active
listener database. Ranking runs against a temporary SQLite backup of the
current listener state, which is removed when the process exits.

Run from the app folder with:
    .venv\\Scripts\\python.exe backend\\benchmark_demo.py \\
        --dataset-zip C:\\path\\to\\liquid-briefing-data.zip \\
        --output docs\\performance-measurements.json
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import time
import tracemalloc
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def measure(function, repeats: int) -> tuple[list[float], list[int]]:
    """Run a callable repeatedly and return wall times and traced peak bytes."""
    durations: list[float] = []
    peaks: list[int] = []
    for _ in range(repeats):
        gc.collect()
        tracemalloc.start()
        started = time.perf_counter()
        result = function()
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        durations.append(elapsed)
        peaks.append(peak)
        del result
    return durations, peaks


def load_source_rows(zip_path: Path) -> list[dict]:
    """Read the original JSONL records using the app's offline input format."""
    rows: list[dict] = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(".jsonl"):
                continue
            content = archive.read(member).decode("utf-8-sig")
            rows.extend(json.loads(line) for line in content.splitlines() if line.strip())
    return rows


def copy_database_read_only(source: Path, destination: Path) -> None:
    """Use SQLite backup API so a live WAL database is read without copying it."""
    source_uri = "file:" + quote(source.resolve().as_posix(), safe="/:") + "?mode=ro"
    reader = sqlite3.connect(source_uri, uri=True)
    writer = sqlite3.connect(destination)
    try:
        reader.backup(writer)
    finally:
        writer.close()
        reader.close()


def import_server_with_temporary_database(snapshot: Path):
    """Import the app ranking function while redirecting import-time init writes."""
    active_db = (ROOT / "data" / "liquid.db").resolve()
    original_connect = sqlite3.connect

    def redirected_connect(database, *args, **kwargs):
        try:
            is_active = Path(database).resolve() == active_db
        except (TypeError, OSError, ValueError):
            is_active = False
        if is_active:
            database = snapshot
        return original_connect(database, *args, **kwargs)

    sqlite3.connect = redirected_connect
    try:
        from backend import server
    finally:
        sqlite3.connect = original_connect

    # Runtime calls after import continue to use the disposable copy.
    server.DB = snapshot
    return server


def summary(durations: list[float], peaks: list[int]) -> dict:
    return {
        "repeat_count": len(durations),
        "wall_seconds": {
            "min": min(durations),
            "median": median(durations),
            "max": max(durations),
            "runs": durations,
        },
        "python_traced_peak_bytes": {
            "max": max(peaks),
            "runs": peaks,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "performance-measurements.json")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    zip_path = args.dataset_zip.expanduser().resolve()
    output_path = args.output.resolve()
    required_output = (ROOT / "docs" / "performance-measurements.json").resolve()
    if not zip_path.is_file():
        parser.error(f"Dataset ZIP not found: {zip_path}")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if output_path != required_output:
        parser.error(f"Output is fixed to {required_output} to protect app data and other files")

    from backend.prepare import ROOT as APP_ROOT, tags_for

    # Time and trace the same JSON parse plus runtime story-index normalization
    # used by the app, without assigning the returned catalog to global state.
    catalog_path = APP_ROOT / "data" / "catalog.json"
    catalog_json_runs, catalog_json_peaks = measure(
        lambda: json.loads(catalog_path.read_text(encoding="utf-8")), args.repeats
    )
    loaded_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_bytes = catalog_path.stat().st_size
    with zipfile.ZipFile(zip_path) as archive:
        jsonl_member_count = sum(name.lower().endswith(".jsonl") for name in archive.namelist())

    zip_rows_runs, zip_rows_peaks = measure(lambda: load_source_rows(zip_path), args.repeats)
    # Keep one parsed dataset in memory for timing the pure tag function.
    source_rows = load_source_rows(zip_path)
    if len(source_rows) != 1740:
        raise RuntimeError(f"Expected 1,740 JSONL records; found {len(source_rows)}")

    tag_runs, tag_peaks = measure(
        lambda: [tags_for(row) for row in source_rows], args.repeats
    )
    scaled_rows = source_rows * 10
    tag_10x_runs, tag_10x_peaks = measure(
        lambda: [tags_for(row) for row in scaled_rows], args.repeats
    )
    # Aggregate counts are computed separately from the timed regions.
    topic_assignments = sum(len(tags_for(row)) for row in source_rows)

    active_db = APP_ROOT / "data" / "liquid.db"
    with tempfile.TemporaryDirectory(prefix="liquid-briefing-benchmark-") as temp_dir:
        snapshot = Path(temp_dir) / "liquid-benchmark.db"
        copy_database_read_only(active_db, snapshot)
        # Import-time schema checks/seeding, if needed, occur only in this copy.
        server = import_server_with_temporary_database(snapshot)
        runtime_catalog_runs, runtime_catalog_peaks = measure(
            server.read_catalog, args.repeats
        )
        profiles = server.profiles()
        if len(profiles) != 7:
            raise RuntimeError(f"Expected 7 demo profiles in the snapshot; found {len(profiles)}")
        profile_ids = [profile["id"] for profile in profiles]
        per_profile_last_run: dict[str, dict] = {}

        def rank_all_profiles() -> dict:
            per_profile: dict[str, dict] = {}
            for profile_id in profile_ids:
                started = time.perf_counter()
                ranked = server.ranked(profile_id, all_items=True)
                per_profile[profile_id] = {
                    "wall_seconds": time.perf_counter() - started,
                    "ranked_story_count": len(ranked),
                }
            per_profile_last_run.clear()
            per_profile_last_run.update(per_profile)
            return {"profile_count": len(per_profile)}

        ranking_runs, ranking_peaks = measure(rank_all_profiles, args.repeats)

    output = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "measurement_clock": "time.perf_counter",
            "memory_measurement": "tracemalloc Python-allocation peak; excludes native allocations and OS RSS",
            "repeats": args.repeats,
            "ranking": "backend.server.ranked(profile_id, all_items=True), using a temporary read-only backup of the current profile database",
            "tagging": "backend.prepare.tags_for on original JSONL records; tag results are held only in memory",
            "synthetic_10x": "same 1,740 parsed record objects repeated ten times (17,400 tag calls); not 17,400 unique articles",
            "mutation_safety": "catalog and active SQLite database were not written; import-time database initialization and ranking used a temporary copy",
        },
        "inputs": {
            "catalog_file_bytes": catalog_bytes,
            "catalog_articles": loaded_catalog.get("stats", {}).get("articles"),
            "catalog_story_records": len(loaded_catalog.get("stories", [])),
            "dataset_jsonl_records": len(source_rows),
            "dataset_feeds": jsonl_member_count,
            "profile_ids": profile_ids,
        },
        "measurements": {
            "catalog_json_read_and_parse": summary(catalog_json_runs, catalog_json_peaks),
            "app_runtime_catalog_load_and_normalization": summary(runtime_catalog_runs, runtime_catalog_peaks),
            "zip_read_and_jsonl_parse": summary(zip_rows_runs, zip_rows_peaks),
            "tag_1740_original_records": {
                **summary(tag_runs, tag_peaks),
                "records_per_run": len(source_rows),
                "topic_assignments_per_run": topic_assignments,
            },
            "tag_17400_synthetic_records": {
                **summary(tag_10x_runs, tag_10x_peaks),
                "records_per_run": len(scaled_rows),
                "topic_assignments_per_run": topic_assignments * 10,
                "unique_source_records": len(source_rows),
            },
            "rank_7_profiles_over_full_catalog": {
                **summary(ranking_runs, ranking_peaks),
                "all_items": True,
                "per_profile_last_run": per_profile_last_run,
                "per_profile_run_total_seconds_last_run": sum(x["wall_seconds"] for x in per_profile_last_run.values()),
            },
        },
        "not_measured": {
            "17_400_unique_article_ingest_or_tagging": "No 17,400 unique records were supplied; the 10x test repeats the provided 1,740 records.",
            "frontier_model_or_embedding_cost": "No model calls were made.",
            "ElevenLabs_or_other_TTS_cost": "No speech-generation calls were made.",
            "cloud_latency_or_production_throughput": "Not measured by this local benchmark.",
            "10x_cost_projection": "Must use explicit model/audio rates and assumptions in the presentation; it is not derived from local timings.",
        },
        "cloud_cost_projection": {
            "status": "unpriced; no provider/model rates or production usage counts were supplied",
            "volume_basis": {
                "articles_full_dataset": 1740,
                "articles_10x": 17400,
                "plain_text_characters_approx_from_dataset_tips": 9000000,
                "plain_text_characters_approx_10x_arithmetic": 90000000,
                "html_characters_approx_from_dataset_tips": 12400000,
                "html_characters_approx_10x_arithmetic": 124000000,
            },
            "projected_usd": {
                "shared_preparation_full_dataset": None,
                "shared_preparation_10x": None,
                "personalized_audio_edition": None,
            },
            "projection_formula": "shared model/embedding input-token usage times the selected vendor rates, plus generated script tokens and TTS characters times the selected voice/model rate, plus declared n8n/cloud overhead",
            "inputs_needed": [
                "selected provider, model, tokenizer, and dated input/output/embedding rates",
                "actual request token counts and whether full article bodies or excerpts are sent",
                "TTS provider/model, billed characters per edition, and dated rate",
                "number of listeners and editions, separated from article volume",
                "n8n/cloud execution and storage assumptions",
            ],
            "source_for_approximate_character_volume": "liquid-briefing-data.zip / IDEAS_AND_TIPS.txt / TIPS, BY JUDGING CRITERION",
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output_path),
        "catalog_story_records": output["inputs"]["catalog_story_records"],
        "dataset_jsonl_records": len(source_rows),
        "profile_count": len(profile_ids),
        "measured": output["measurements"],
        "not_measured": output["not_measured"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
