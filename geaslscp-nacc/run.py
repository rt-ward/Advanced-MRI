#!/usr/bin/env python3
"""Flywheel Gear: GEASLscp-nacc.

This gear:
1. Reads gear inputs and config via GearContext.
2. Runs pipeline_singlePLD.sh (from the kjobson/geaslscp base image) with
   flags built from the gear config. The pipeline itself writes the
   Flywheel metadata (via workflows/flywheel_context.py).
3. Checks that the expected CBF output exists.
"""

import logging
import os
from pathlib import Path

from fw_gear.context import GearContext
from fw_gear.utils.wrapper import exec_command

log = logging.getLogger(__name__)

PIPELINE_SCRIPT = "/flywheel/v0/pipeline_singlePLD.sh"


def fmt(value) -> str:
    """Format a config number like jq does (3.0 -> "3"); the pipeline uses
    avg in integer shell arithmetic."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def build_command(context: GearContext) -> list[str]:
    """Build the pipeline_singlePLD.sh command from gear inputs and config."""
    config = context.config.opts

    cmd = [
        "/bin/bash",
        PIPELINE_SCRIPT,
        "-a",
        str(context.config.get_input_path("dicom_nifti_asl")),
    ]

    m0_path = context.config.get_input_path("nifti_m0")
    if m0_path is not None:
        cmd.extend(["-m", str(m0_path)])

    # Optional overrides; ld/pld/avg are only used by the pipeline if all
    # three are set, otherwise it reads them from the DICOM-derived JSON.
    for key, flag in [("ld", "-l"), ("pld", "-p"), ("avg", "-n"), ("alpha", "-g")]:
        value = config.get(key)
        if value is not None:
            cmd.extend([flag, fmt(value)])

    if config.get("skip_extended", False):
        cmd.append("-e")

    return cmd


def check_outputs(context: GearContext) -> None:
    """Raise if the CBF map was not produced."""
    output_dir = Path(context.output_dir)
    # <subject_id>_cbf.nii.gz, or cbf.nii.gz if no subject ID
    pattern = "*cbf.nii.gz"

    matches = list(output_dir.glob(pattern))
    if not matches:
        raise RuntimeError(f"No CBF map found in {output_dir} matching {pattern}")
    log.info(f"Found CBF output: {matches[0]}")


def main(context: GearContext) -> None:
    """Execute main gear workflow."""
    cmd = build_command(context)
    log.info(f"Running pipeline: {cmd}")
    # Put /opt/gear-bin first so the pipeline's `python3` is the system Python
    # (which has its packages), not FSL's.
    env = {"PATH": "/opt/gear-bin:" + os.environ.get("PATH", "")}
    exec_command(cmd, stream=True, environ=env)  # raises RuntimeError on non-zero exit

    check_outputs(context)
    log.info("GEASLscp-nacc gear completed successfully.")


if __name__ == "__main__":
    with GearContext() as context:
        context.init_logging()
        context.log_config()
        main(context)
