#!/usr/bin/env python3
"""
Flywheel Gear: QSMxT Processing Pipeline.

This gear:
1. Unzips MEGRE and T1w DICOM archives.
2. Converts MEGRE using `dicom-convert`.
3. Converts T1w DICOMs using `dcm2niix`.
4. Launches QSMxT with user-provided config options.
5. Collects workflow outputs, standard NIfTI results, and crash logs.
6. Packages results into artifacts suitable for Flywheel.

Environment Assumptions:
- QSMxT, dicom-convert, and dcm2niix are already installed in the container.
- Filesystem paths /dicoms, /bids, /qsm are writable.
"""

import glob
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import flywheel


def run_cmd(cmd: list[str], description: str):
    """Run a shell command with logging + error trapping."""
    print(f"\n[CMD] {description}: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"Command failed during: {description}")

    return result


def flywheel_run():
    """Execute main Flywheel gear workflow."""
    with flywheel.GearContext() as context:
        config = context.config
        dicom_megre_zip = context.get_input_path("input_file")
        dicom_t1w_zip = context.get_input_path("anatomical")
        out_dir = context.output_dir

    ###########################################################################
    # Step 1: Unzip MEGRE DICOMs
    ###########################################################################
    print(f"Unzipping MEGRE DICOMs: {dicom_megre_zip}")
    with zipfile.ZipFile(dicom_megre_zip, "r") as zf:
        zf.extractall("/dicoms/qsm")

    ###########################################################################
    # Step 2: Convert MEGRE DICOMs to BIDS using dicom-convert
    ###########################################################################
    run_cmd(
        [
            "dicom-convert",
            "/dicoms/",
            "/bids/",
            "--auto_yes",
        ],
        description="DICOM to BIDS conversion (MEGRE)",
    )

    ###########################################################################
    # Step 3: Unzip T1w anatomical DICOMs
    ###########################################################################
    print(f"Unzipping T1w DICOMs: {dicom_t1w_zip}")
    with zipfile.ZipFile(dicom_t1w_zip, "r") as zf:
        zf.extractall("/dicoms/T1w")

    ###########################################################################
    # Step 4: Convert T1w DICOMs into BIDS-compatible naming
    ###########################################################################
    anat_list = list(Path("/bids/").glob("sub*/ses*/anat/*.nii"))
    t1_target_name = None

    if anat_list:
        # Derive subject/session from existing BIDS file
        first_file = anat_list[0]
        important_parts = [
            s for s in first_file.name.split("_") if "sub" in s or "ses" in s
        ]
        t1_target_name = [*important_parts, "T1w"]

        run_cmd(
            [
                "dcm2niix",
                "-b",
                "y",
                "-f",
                t1_target_name,
                "-o",
                str(first_file.parent),
                "/dicoms/T1w/",
            ],
            description="T1w DICOM to NIfTI conversion",
        )
    else:
        print("WARNING: No MEGRE anat/*.nii found. Skipping T1w renaming.")

    ###########################################################################
    # Step 5: Run QSMxT
    ###########################################################################
    qsmxt_cmd = [
        "qsmxt",
        "/bids",
        "/qsm",
        "--premade",
        str(config.get("premade", "False")),
        "--do_qsm",
        "--do_swi",
        "--do_segmentation",
        "--auto_yes",
    ]

    # Append optional custom arguments
    extra_args = config.get("qsmxt_cmd_args", "")
    if extra_args:
        qsmxt_cmd += extra_args.split()

    run_cmd(qsmxt_cmd, description="QSMxT processing")

    ###########################################################################
    # Step 6: Package workflow outputs
    ###########################################################################
    workflow_path = "/qsm/workflow"
    workflow_zip = os.path.join(out_dir, "workflow.zip")

    print(f"Packaging workflow directory → {workflow_zip}")
    shutil.make_archive(os.path.splitext(workflow_zip)[0], "zip", workflow_path)

    # Delete expanded workflow to reduce artifact size
    shutil.rmtree(workflow_path, ignore_errors=True)

    ###########################################################################
    # Step 7: Extract and copy resulting NIfTI files into the Flywheel view
    ###########################################################################
    nifti_files = glob.glob("/qsm/**/*.nii", recursive=True)
    print("NIfTI files detected:", nifti_files)

    for f in nifti_files:
        shutil.copy2(f, os.path.join(out_dir, os.path.basename(f)))

    # Create a zip of the entire qsm output tree
    shutil.make_archive(os.path.join(out_dir, "qsm"), "zip", "/qsm/")

    ###########################################################################
    # Step 8: Capture crash files if any
    ###########################################################################
    crash_files = glob.glob("/flywheel/v0/crash*.pklz")
    if crash_files:
        crash_zip = os.path.join(out_dir, "crashes.zip")
        print("Packaging crash reports:", crash_zip)

        with zipfile.ZipFile(crash_zip, "w") as zf:
            for crash in crash_files:
                zf.write(crash, os.path.basename(crash))

        print("ERROR: Crashes detected. Inspect workflow.zip and crashes.zip.")
        sys.exit(1)

    print("QSMxT Gear completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    flywheel_run()
