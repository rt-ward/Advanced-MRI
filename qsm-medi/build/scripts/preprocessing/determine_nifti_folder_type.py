# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

import os
import re
import json
import sys

output_folder = os.environ['OUTPUT_FOLDER']

path_config_json=sys.argv[1]
path_dcm2niix_folder=f'{output_folder}/temp_dcm2niix'
common_prefix_config=None
try:
    # Open the JSON file in read mode ('r') using a 'with' statement
    # The 'with' statement ensures the file is properly closed even if errors occur
    with open(path_config_json, 'r') as file:
        # Load the JSON data from the file
        data = json.load(file)

    common_prefix_config=data.get('load_nifti_common_prefix',None)

except FileNotFoundError:
    pass
except json.JSONDecodeError:
    raise Exception(f"Error: Failed to decode JSON from '{path_config_json}'. The file might contain invalid JSON.")
except Exception as e:
    raise Exception(f"An unexpected error occurred: {e}")


list_files=os.listdir(path_dcm2niix_folder)
list_files_nii=[os.path.basename(nii_file) for nii_file in list_files if nii_file.endswith('.nii')]
# print(list_files_nii)

# Find the common prefix from the nii files
common_prefix = os.path.commonprefix(list_files_nii)
if not common_prefix and common_prefix_config is None:
    raise ValueError("ERROR: No common base name found among the provided paths. Provide a value for load_nifti_common_prefix in config")
print(f"Common prefix from dcm2niix outputs: '{common_prefix}'")

if common_prefix_config is not None:
    print(f"INFO: Replacing common prefix found from dcm2niix ({common_prefix}) with that found from config ({common_prefix_config})")
    common_prefix = common_prefix_config
orig_common_prefix = common_prefix

# Count number of echoes:
single_file=False
pattern=fr'{common_prefix}\d*\.nii'
echo_match = [nii_file for nii_file in list_files_nii if bool(re.search(pattern,nii_file))]
if len(echo_match) > 1:
    num_echoes=len(echo_match)
    common_prefix=f'{common_prefix}\d*'
elif len(echo_match) == 1:
    single_file=True
    num_echoes=-1
else:
    print("INFO: Failed to expected mag data with no suffix. Trying to find real data.")
    pattern = fr'{common_prefix}\d*_real\.nii'
    echo_match = [nii_file for nii_file in list_files_nii if bool(re.search(pattern, nii_file))]
    if len(echo_match) > 1:
        num_echoes = len(echo_match)
        common_prefix = f'{common_prefix}\d*'
    elif len(echo_match) == 1:
        single_file = True
        num_echoes = -1
    else:
        raise Exception(f"ERROR: Unable to find a nifti file that has a common base prefix of regex pattern - {pattern}")

phase_exists=False
real_exists=False
imaginary_exists=False

# Check if phase images exist
pattern=fr'{common_prefix}_ph\.nii'
phase_match = [nii_file for nii_file in list_files_nii if bool(re.search(pattern,nii_file))]
if len(phase_match) > 0:
    phase_exists=True

# Check if real images exist
pattern=fr'{common_prefix}_real\.nii'
real_match = [nii_file for nii_file in list_files_nii if bool(re.search(pattern,nii_file))]
if len(real_match) > 0:
    real_exists=True

# Check if imaginary images exist
pattern=fr'{common_prefix}_imaginary\.nii'
imaginary_match = [nii_file for nii_file in list_files_nii if bool(re.search(pattern,nii_file))]
if len(imaginary_match) > 0:
    imaginary_exists=True

meta_data={
    "common_prefix":orig_common_prefix,
    "num_echoes":num_echoes,
    "single_file":int(single_file),
    "phase_exists":int(phase_exists),
    "real_exists":int(real_exists),
    "imaginary_exists":int(imaginary_exists)
}

with open(f'{output_folder}/temp_dcm2niix/meta_data.json', 'w', encoding='utf-8') as f:
    json.dump(meta_data, f, ensure_ascii=False, indent=4)