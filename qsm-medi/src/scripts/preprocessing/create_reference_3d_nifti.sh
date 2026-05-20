#!/bin/bash
# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

input_data_type=$1

rm -rf ${OUTPUT_FOLDER}/temp_dcm2niix
mkdir -p ${OUTPUT_FOLDER}/temp_dcm2niix

if [[ "$input_data_type" == "dicom" ]]; then
  dcm2niix -z n -i y -f '%p_%s' -o ${OUTPUT_FOLDER}/temp_dcm2niix ${INPUT_FOLDER}/dicom_data
elif [[ "$input_data_type" == "nifti" ]]; then
  cp -r ${INPUT_FOLDER}/nifti/*.ni* ${OUTPUT_FOLDER}/temp_dcm2niix
  cp -r ${INPUT_FOLDER}/nifti/*.json ${OUTPUT_FOLDER}/temp_dcm2niix
  gunzip -f ${OUTPUT_FOLDER}/temp_dcm2niix/*.ni*
fi

#find first nifti file
path_ref_nii=$(find ${OUTPUT_FOLDER}/temp_dcm2niix -maxdepth 1 -type f -name "*.nii" -print -quit)
cp ${path_ref_nii} ${OUTPUT_FOLDER}/temp_dcm2niix/ref_image_pre.nii
python3 /opt/process_QSM/preprocessing/check_reference_nii.py 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log
rm -rf ${OUTPUT_FOLDER}/temp_dcm2niix/ref_image_pre.nii