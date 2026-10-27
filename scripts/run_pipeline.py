"""Run the OpenMobility AI data pipeline."""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "storage" / "processed" / "gtfs" / "idfm"
TRANSFORMATIONS_DIR = ROOT / "transformations"
VALIDATOR_SCRIPT = ROOT / "scripts" / "validate_gtfs_outputs.py"
INGESTION_SCRIPT = ROOT / "ingestion" / "gtfs.py"
INTEGRITY_SCRIPT = ROOT / "scripts" / "check_gtfs.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def find_dbt_executable() -> str:
    """Find dbt in the project's virtual environment or PATH."""
    candidates = [
        ROOT / ".venv" / "Scripts" / "dbt.exe",
        ROOT / ".venv" / "bin" / "dbt",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    dbt_in_path = shutil.which("dbt")
    if dbt_in_path:
        return dbt_in_path

    raise FileNotFoundError(
        "Could not find dbt. Install it in the project "
        "virtual environment before running the pipeline."
    )


def run_step(
    name: str,
    command: list[str],
    env: dict[str, str],
) -> None:
    """Run a pipeline step and stop immediately if it fails."""
    logger.info("Starting: %s", name)

    subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=True,
    )

    logger.info("Completed: %s", name)


def main() -> int:
    """Execute the pipeline and return an exit code."""
    parser = argparse.ArgumentParser(
        description="Run the OpenMobility AI GTFS and dbt pipeline."
    )
    parser.add_argument(
        "--ingest-gtfs",
        action="store_true",
        help="Reprocess the GTFS ZIP before validation and dbt.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help=(
            "Update the GTFS validation baseline only after "
            "all pipeline steps succeed."
        ),
    )
    args = parser.parse_args()

    env = os.environ.copy()
    env["OPENMOBILITY_PROCESSED_DIR"] = str(
        PROCESSED_DIR.resolve()
    )

    try:
        if not args.ingest_gtfs and not PROCESSED_DIR.is_dir():
            raise FileNotFoundError(
                f"Processed GTFS directory not found: {PROCESSED_DIR}. "
                "Run with --ingest-gtfs to generate the data."
            )

        if args.ingest_gtfs:
            run_step(
                "GTFS ingestion",
                [
                    sys.executable,
                    str(INGESTION_SCRIPT),
                ],
                env,
            )

        run_step(
            "GTFS output validation",
            [
                sys.executable,
                str(VALIDATOR_SCRIPT),
            ],
            env,
        )

        run_step(
            "GTFS integrity checks",
            [
                sys.executable,
                str(INTEGRITY_SCRIPT),
            ],
            env,
        )

        dbt = find_dbt_executable()

        run_step(
            "dbt build",
            [
                dbt,
                "build",
                "--project-dir",
                str(TRANSFORMATIONS_DIR),
                "--profiles-dir",
                str(TRANSFORMATIONS_DIR),
            ],
            env,
        )

        # Update the baseline only after every preceding step succeeds.
        if args.update_baseline:
            run_step(
                "Update GTFS validation baseline",
                [
                    sys.executable,
                    str(VALIDATOR_SCRIPT),
                    "--update-baseline",
                ],
                env,
            )

    except subprocess.CalledProcessError as exc:
        logger.error(
            "Pipeline failed: command exited with code %s.",
            exc.returncode,
        )
        return exc.returncode or 1

    except (FileNotFoundError, OSError) as exc:
        logger.error("Pipeline could not run: %s", exc)
        return 1

    logger.info("OpenMobility AI pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
