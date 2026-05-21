#/bin/bash
# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

output_location="${OUTPUT_FOLDER}/pipeline_meta.txt"
input_arguments="$*"
#path_parameter_file="${INPUT_FOLDER}/parameters/qsm_parameters.json" # handled by exported variable
config_name=""

echo "QSM-MEDI Pipeline v${PIPELINE_VERSION}" >> ${output_location}
echo "Developed for use in the CLARiTI consortium by Dr. Arnold Evia (Arnold_Evia@rush.edu) from the Rush Alzheimer's Disease Center." >> ${output_location}
echo "For any questions, please email Dr. Evia." >> ${output_location}
echo "" >> ${output_location}
echo "Started on $(date)" >> ${output_location}
echo "Input arguments: ${input_arguments}" >> ${output_location}

if [ -e "${PATH_PARAMETERS_JSON}" ]; then
  echo "INFO: Found custom pipeline parameter file. Here are the contents:" >> ${output_location}
  cat ${PATH_PARAMETERS_JSON} >> ${output_location}
else
  echo "INFO: Did not find custom pipeline parameter file." >> ${output_location}
fi