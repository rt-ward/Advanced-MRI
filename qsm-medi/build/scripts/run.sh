#!/bin/bash
# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

num_threads_hdbet=0 #use all available threads

export INPUT_FOLDER="/input"
export OUTPUT_FOLDER="/output"

export PATH_PARAMETERS_JSON="${INPUT_FOLDER}/parameters/qsm_parameters.json"
export PIPELINE_VERSION="2.2.0"
custom_parameters_json_set=0
input_dicom_exists=0
input_nifti_exists=0
input_data_type=""
config_name=""

while getopts "n:c:i:o:p:" opt; do
  case $opt in
    n)
      num_threads_hdbet=${OPTARG}
      ;;
    c)
      config_name=${OPTARG}
      custom_parameters_json_set=1
      ;;
    i)
      export INPUT_FOLDER=${OPTARG}
      echo "INFO: INPUT_FOLDER set to ${INPUT_FOLDER}"
      export PATH_PARAMETERS_JSON="${INPUT_FOLDER}/parameters/qsm_parameters.json"
      ;;
    o)
      export OUTPUT_FOLDER=${OPTARG}
      echo "INFO: OUTPUT_FOLDER set to ${OUTPUT_FOLDER}"
      ;;
    p)
      export PATH_PARAMETERS_JSON=${OPTARG}
      echo "INFO: PATH_PARAMETERS_JSON set to ${PATH_PARAMETERS_JSON}"
      custom_parameters_json_set=1
      ;;
    \?)
      echo "ERROR: Unknown option: -${OPTARG}" >&2
      exit 1
      ;;
  esac
done

echo "QSM-MEDI Pipeline v${PIPELINE_VERSION}" | tee -a ${OUTPUT_FOLDER}/processing.log
echo "Developed for use in the CLARiTI consortium by Dr. Arnold Evia (Arnold_Evia@rush.edu) from the Rush Alzheimer's Disease Center." | tee -a ${OUTPUT_FOLDER}/processing.log
echo "For any questions, please email Dr. Evia." | tee -a ${OUTPUT_FOLDER}/processing.log
echo "" | tee -a ${OUTPUT_FOLDER}/processing.log
echo "*** IMPORTANT: PLEASE CITE WORKS BELOW WHEN USING THIS CONTAINER ***" | tee -a ${OUTPUT_FOLDER}/processing.log
echo " - hd-bet, doi: 10.1002/hbm.24750" | tee -a ${OUTPUT_FOLDER}/processing.log
echo " - mSMV, doi: 10.1002/mrm.29963" | tee -a ${OUTPUT_FOLDER}/processing.log
echo " - Nonlinear fitting, doi: 10.1002/mrm.24272" | tee -a ${OUTPUT_FOLDER}/processing.log
echo " - ROMEO phase unwrapping, doi: 10.1002/mrm.28563" | tee -a ${OUTPUT_FOLDER}/processing.log
echo " - PDF background field removal, doi: 10.1002/nbm.1670" | tee -a ${OUTPUT_FOLDER}/processing.log
echo " - ARLO R2s fitting, doi: 10.1002/mrm.25137" | tee -a ${OUTPUT_FOLDER}/processing.log
echo " - Homogeneity mask (CSF mask), doi: 10.1111/jon.12923" | tee -a ${OUTPUT_FOLDER}/processing.log
echo " - MEDI reconstruction, doi: 10.1016/j.neuroimage.2011.08.082" | tee -a ${OUTPUT_FOLDER}/processing.log
echo "********************************************************************" | tee -a ${OUTPUT_FOLDER}/processing.log
echo "" | tee -a ${OUTPUT_FOLDER}/processing.log

if [[ -n "${config_name}" ]]; then
  export PATH_PARAMETERS_JSON="/config/${config_name}.json"
fi

if [[ "${custom_parameters_json_set}" -eq 1 && ! -f "${PATH_PARAMETERS_JSON}" ]]; then
  echo "ERROR: A custom parameter file was set, but ${PATH_PARAMETERS_JSON} does not exist"
  exit 1
fi

rm -rf ${OUTPUT_FOLDER}/pipeline_meta.txt
/opt/process_QSM/preprocessing/create_pipeline_meta.sh $@
cp -f ${OUTPUT_FOLDER}/pipeline_meta.txt ${OUTPUT_FOLDER}/processing.log
rm -rf ${OUTPUT_FOLDER}/reference_3d.ni*
rm -rf ${OUTPUT_FOLDER}/temp_*
rm -rf ${OUTPUT_FOLDER}/QSM_mask.ni*
rm -rf ${OUTPUT_FOLDER}/QSM.ni*

if [ -d "${INPUT_FOLDER}/dicom_data" ]; then
  input_dicom_exists=1
fi
if [ -d "${INPUT_FOLDER}/nifti" ]; then
  input_nifti_exists=1
fi

if [[ "$input_dicom_exists" -eq 1 && "$input_nifti_exists" -eq 1 ]]; then
  echo "WARNING: Both dicom and nifti input data exist. Continuing processing with nifti input data." | tee -a ${OUTPUT_FOLDER}/processing.log
  input_data_type="nifti"
elif [[ "$input_dicom_exists" -eq 1 && "$input_nifti_exists" -eq 0 ]]; then
  input_data_type="dicom"
elif [[ "$input_dicom_exists" -eq 0 && "$input_nifti_exists" -eq 1 ]]; then
  input_data_type="nifti"
elif [[ "$input_dicom_exists" -eq 0 && "$input_nifti_exists" -eq 0 ]]; then
  echo "ERROR: No input data (dicom or nifti) were found. Dicom data must be mounted to ${INPUT_FOLDER}/dicom_data or nifti data must be mounted to ${INPUT_FOLDER}/nifti" | tee -a ${OUTPUT_FOLDER}/processing.log
  exit 1
fi

if ! python3 /opt/process_QSM/preprocessing/create_reference_3d_nifti.py ${input_data_type} ${PATH_PARAMETERS_JSON} 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log; then
  echo "ERROR: Could not create reference 3d nifti"
  exit 1
fi

if ! python3 /opt/process_QSM/preprocessing/determine_nifti_folder_type.py ${PATH_PARAMETERS_JSON} 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log; then
  echo "ERROR: Could not determine data in nifti folder"
  exit 1
fi

cd ${OUTPUT_FOLDER}
if [ -f "${INPUT_FOLDER}/custom/QSM_mask.nii.gz" ]; then
  gunzip ${INPUT_FOLDER}/custom/QSM_mask.nii.gz
fi
if [ ! -f "${INPUT_FOLDER}/custom/QSM_mask.nii" ]; then
  /opt/process_QSM/for_redistribution_files_only/run_pipeline_qsm.sh /opt/MCR-2018b/v95 pre_hdbet ${PATH_PARAMETERS_JSON} ${OUTPUT_FOLDER} 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log
  if [ ! -f "${OUTPUT_FOLDER}/temp_iMag.nii" ]; then
    echo "ERROR: Could not create magnitude image for hd-bet"
    exit 1
  fi
  python3 /opt/process_QSM/hd-bet/prep_image_for_hdbet.py 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log
  start=`date +%s`
  hd-bet -i ${OUTPUT_FOLDER}/temp_hd-bet_input.nii.gz -o ${OUTPUT_FOLDER}/temp_hd-bet_output_pre.nii.gz -device cpu -threads ${num_threads_hdbet} -mode fast -tta 0 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log
  end=`date +%s`
  runtime=$((end-start))
  echo "hd-bet runtime: ${runtime} seconds" 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log
  python3 /opt/process_QSM/hd-bet/post_for_hdbet.py 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log
fi

/opt/process_QSM/for_redistribution_files_only/run_pipeline_qsm.sh /opt/MCR-2018b/v95 execute ${PATH_PARAMETERS_JSON} ${OUTPUT_FOLDER} 2>&1 | tee -a ${OUTPUT_FOLDER}/processing.log
if [ ! -f "${OUTPUT_FOLDER}/QSM.nii" ]; then
  echo "ERROR: QSM pipeline failed during MEDI processing"
  exit 2
fi
rm -rf ${OUTPUT_FOLDER}/temp_reference_3d.nii
rm -rf ${OUTPUT_FOLDER}/temp_dcm2niix
rm -rf ${OUTPUT_FOLDER}/results

gzip -f ${OUTPUT_FOLDER}/*.nii
