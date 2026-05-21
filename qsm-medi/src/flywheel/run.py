#!/usr/bin/env python
# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause


import json
import os
import subprocess
import time
import zipfile

import flywheel

path_parameters_json = "/input/parameters/qsm_parameters.json"


def run_command_with_subprocess(command):
    terminal_env = os.environ.copy()

    def stream_process(process):
        go = process.poll() is None
        for line in process.stdout:
            print(line, end="")
        return go

    process = subprocess.Popen(
        args=command,
        env=terminal_env,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    while stream_process(process):
        time.sleep(0.1)
    return process.returncode


def create_parameters_json_from_flywheel_context(input_context):
    list_config_variables = [
        "load_nifti_common_prefix",
        "load_negate_every_other_axis",
        "invert_phase",
        "method_phase_unwrap",
        "phase_corr",
        "csf_thresh_R2s",
        "csf_flag_erode",
        "pdf_tol",
        "pdf_n_cg",
        "pdf_space",
        "pdf_n_pad",
        "prefilter",
        "bipolar_complex_fit",
        "debug_mode",
        "medi_msmv",
        "medi_lambda",
        "medi_max_iter",
        "tol_norm_ratio",
        "medi_cg_verbose",
        "medi_cg_max_iter",
        "medi_cg_tol",
    ]

    os.makedirs(os.path.dirname(path_parameters_json), exist_ok=False)

    parameters_dict = {}
    for config_variable in list_config_variables:
        config_value = input_context.config.get(config_variable)
        if config_value is not None:
            parameters_dict[config_variable] = config_value

    with open(path_parameters_json, "w", encoding="utf-8") as f:
        json.dump(parameters_dict, f, ensure_ascii=False, indent=4)


input_folder = "/flywheel/input"
unzip_destination = f"{input_folder}/dicom_data"


with flywheel.GearContext() as context:
    config = context.config

    dicom_megre_zip = []
    dicom_megre_zip.append(context.get_input_path("input_file"))
    dicom_megre_zip.append(context.get_input_path("input_file_opt"))
    out_dir = context.output_dir

    print(f"Unzipping MEGRE DICOMs: {dicom_megre_zip}")
    for i in range(len(dicom_megre_zip)):
        if dicom_megre_zip[i] is not None:
            unzip_destination_for_i = f"{unzip_destination}/{i}"
            os.makedirs(unzip_destination_for_i, exist_ok=True)
            with zipfile.ZipFile(dicom_megre_zip[i], "r") as zf:
                zf.extractall(unzip_destination_for_i)

    output_folder = context.output_dir

    num_threads_hdbet = context.config.get("num_threads_hdbet")
    if num_threads_hdbet is None:
        num_threads_hdbet = 0

    create_parameters_json_from_flywheel_context(context)
    pipeline_command = (
        f"/opt/process_QSM/run.sh -i {input_folder} -o {output_folder} "
        f"-p {path_parameters_json} -n {num_threads_hdbet}"
    ).split()
    returncode = run_command_with_subprocess(pipeline_command)

    if returncode != 0:
        raise Exception("ERROR: run.sh returned a non-zero exit code. See error above")

    if not os.path.isfile(f"{output_folder}/QSM.nii.gz"):
        raise Exception(
            "ERROR: Final check failed - QSM image was not created. See error above"
        )
