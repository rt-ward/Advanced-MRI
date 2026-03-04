#!/usr/bin/env python
# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

import flywheel
import json
import os
import shutil
import subprocess
import time
import zipfile

path_parameters_json = '/input/parameters/qsm_parameters.json'

def unzip_all(zip_file_path, extract_to_path):
    """
    Unzips all contents of a specified ZIP file to a target directory.

    Args:
        zip_file_path (str): The path to the ZIP file.
        extract_to_path (str): The path to the directory where contents will be extracted.
    """
    if not os.path.exists(extract_to_path):
        os.makedirs(extract_to_path)

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to_path)
    # print(f"All contents of '{zip_file_path}' extracted to '{extract_to_path}'")

def run_command_with_subprocess(command):
    terminal_env = os.environ.copy()
    def stream_process(process):
        go = process.poll() is None
        for line in process.stdout:
            print(line, end='')
        return go

    process = subprocess.Popen(args=command, env=terminal_env, shell=False, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, universal_newlines=True)
    while stream_process(process):
        time.sleep(0.1)

def create_parameters_json_from_flywheel_context(context):
    list_config_variables = ['load_nifti_common_prefix', 'load_negate_every_other_axis', 'invert_phase',
                             'method_phase_unwrap', 'phase_corr',
                             'csf_thresh_R2s', 'csf_flag_erode',
                             'pdf_tol', 'pdf_n_cg', 'pdf_space', 'pdf_n_pad',
                             'prefilter', 'medi_msmv', 'medi_lambda', 'medi_max_iter', 'tol_norm_ratio',
                             'medi_cg_verbose', 'medi_cg_max_iter', 'medi_cg_tol']

    os.makedirs(os.path.dirname(path_parameters_json), exist_ok=False)

    parameters_dict={}
    for config_variable in list_config_variables:
        config_value = context.config.get(config_variable)
        if config_value is not None:
            parameters_dict[config_variable]=config_value

    with open(path_parameters_json, 'w', encoding='utf-8') as f:
        json.dump(parameters_dict, f, ensure_ascii=False, indent=4)

# base_folder = '/flywheel/v0'
gear_context = flywheel.GearContext()

input_folder='/flywheel/input'
unzip_destination=f'{input_folder}/dicom_data'
input_zip_file=gear_context.get_input_path('gre_data')
unzip_all(input_zip_file,unzip_destination)

output_folder=gear_context.output_dir

num_threads_hdbet=gear_context.config.get('num_threads_hdbet')
if num_threads_hdbet is None:
    num_threads_hdbet = 0

create_parameters_json_from_flywheel_context(gear_context)
pipeline_command=f'/opt/process_QSM/run.sh -i {input_folder} -o {output_folder} -p {path_parameters_json} -n {num_threads_hdbet}'.split()
run_command_with_subprocess(pipeline_command)