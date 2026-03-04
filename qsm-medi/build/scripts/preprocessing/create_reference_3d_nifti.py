# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

import os
import json
import sys
import shutil
import subprocess
import time
import glob
import nibabel

input_folder = os.environ['INPUT_FOLDER']
output_folder = os.environ['OUTPUT_FOLDER']

input_data_type=sys.argv[1]
path_config_json=sys.argv[2]
path_dcm2niix_folder=f'{output_folder}/temp_dcm2niix'
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


try:
  shutil.rmtree(path_dcm2niix_folder)
except FileNotFoundError:
  pass
except OSError as e:
  print(f"ERROR: Unexpected exception encountered - {e}")

os.makedirs(path_dcm2niix_folder, exist_ok=True)

if input_data_type == "dicom":
  run_command_with_subprocess(f"dcm2niix -z n -i y -f %p_%s -o {output_folder}/temp_dcm2niix {input_folder}/dicom_data".split())
  # find first nifti file
  found_nifti = glob.glob(f"{output_folder}/temp_dcm2niix/*.nii")[0]
  shutil.copy(found_nifti, f"{output_folder}/temp_dcm2niix/ref_image_pre.nii")
elif input_data_type == "nifti":
  for wildcard_pattern in ['*.ni*','*.json']:
    search_pattern = os.path.join("/input/nifti/",wildcard_pattern)
    found_files = glob.glob(search_pattern)
    for file in found_files:
      shutil.copy(file,path_dcm2niix_folder)

  for zipped_file in glob.glob(f'{output_folder}/temp_dcm2niix/*.ni*'):
    run_command_with_subprocess(f'gunzip -f {zipped_file}'.split())

  search_pattern = f"{output_folder}/temp_dcm2niix/*.nii"
  if os.path.isfile(path_config_json):
    with open(path_config_json, 'r') as config_file:
      # Load the JSON data from the file into a Python dictionary
      config = json.load(config_file)
      load_nifti_common_prefix = config.get('load_nifti_common_prefix')
      if load_nifti_common_prefix:
        search_pattern=f"{output_folder}/temp_dcm2niix/{load_nifti_common_prefix}*.nii"

  found_nifti = glob.glob(search_pattern)[0]
  shutil.copy(found_nifti, f"{output_folder}/temp_dcm2niix/ref_image_pre.nii")


# Reference 3d nii must be 3 dimensional, if not, then change to 3d
img = nibabel.load(f'{output_folder}/temp_dcm2niix/ref_image_pre.nii')
image_dimensions = img.shape
if len(image_dimensions) == 3:
    nibabel.save(img, f'{output_folder}/temp_reference_3d.nii')
elif len(image_dimensions) == 4:
    data4d=img.get_fdata()
    data3d=data4d[...,0]
    img3d=nibabel.nifti1.Nifti1Image(data3d,img.affine,header=img.header)
    nibabel.save(img3d, f'{output_folder}/temp_reference_3d.nii')
else:
    raise ValueError(f"ERROR: ref_image_pre has unexpected number of dimensions = {len(image_dimensions)}")

os.remove(f'{output_folder}/temp_dcm2niix/ref_image_pre.nii')
