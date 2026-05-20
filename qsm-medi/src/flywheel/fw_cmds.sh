# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause


cd ../../
./create_docker.sh

flyw gear build .
flyw gear config --new
#flyw gear config --input input_file=src/flywheel/test/input/gre_data/MEGRE_uw_sag_protocol.zip
#flyw gear run --prepare -d src/flywheel/test/output/local_run_single_zip
#flyw gear run src/flywheel/test/output/local_run_single_zip  -- -e FLYWHEEL_API_KEY=${FLYWHEEL_API_KEY}
#
#flyw gear config --new
#flyw gear config --input input_file=src/flywheel/test/input/gre_data_2_zips/13-CLARITI_NACC874518_MR_CLARiTI_AdvMRI_QSM_GRAPPA3.zip --input input_file_opt=src/flywheel/test/input/gre_data_2_zips/14-CLARITI_NACC874518_MR_CLARiTI_AdvMRI_QSM_GRAPPA3.zip
#flyw gear run --prepare -d src/flywheel/test/output/local_run_2_zips
#flyw gear run src/flywheel/test/output/local_run_2_zips -- -e FLYWHEEL_API_KEY=${FLYWHEEL_API_KEY}
#
#flyw gear config --new
#flyw gear config --input input_file=src/flywheel/test/input/gre_data_2_zips_2/5-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip --input input_file_opt=src/flywheel/test/input/gre_data_2_zips_2/6-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip
#flyw gear run --prepare -d src/flywheel/test/output/local_run_2_zips_2
#flyw gear run src/flywheel/test/output/local_run_2_zips_2 -- -e FLYWHEEL_API_KEY=${FLYWHEEL_API_KEY}

#flyw gear config --new
#flyw gear config --input input_file=test/input/subject0/5-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip --input input_file_opt=test/input/subject0/6-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip -c bipolar_complex_fit=1 -c phase_corr=0
#flyw gear run --prepare -d src/flywheel/test/output/local_run_2_zips_bipolar2
#flyw gear run src/flywheel/test/output/local_run_2_zips_bipolar2 -- -e FLYWHEEL_API_KEY=${FLYWHEEL_API_KEY}

#flyw gear config --new
#flyw gear config --input input_file=test/input/subject0/5-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip --input input_file_opt=test/input/subject0/6-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip -c bipolar_complex_fit=1 -c phase_corr=0
#flyw gear run --prepare -d src/flywheel/test/output/local_run_2_zips_bipolarmin3
#flyw gear run src/flywheel/test/output/local_run_2_zips_bipolarmin3 -- -e FLYWHEEL_API_KEY=${FLYWHEEL_API_KEY}

#flyw gear config --new
#flyw gear config --input input_file=test/input/subject0/5-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip --input input_file_opt=test/input/subject0/6-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip -c bipolar_complex_fit=1 -c phase_corr=0 -c medi_lambda=833.33
#flyw gear run --prepare -d src/flywheel/test/output/local_run_2_zips_bipolarmin3lamb833p33
#flyw gear run src/flywheel/test/output/local_run_2_zips_bipolarmin3lamb833p33 -- -e FLYWHEEL_API_KEY=${FLYWHEEL_API_KEY}

#flyw gear config --new
#flyw gear config --input input_file=test/input/subject0/5-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip --input input_file_opt=test/input/subject0/6-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip -c bipolar_complex_fit=1 -c phase_corr=1
#flyw gear run --prepare -d src/flywheel/test/output/local_run_2_zips_bipolarmin3phasecorr
#flyw gear run src/flywheel/test/output/local_run_2_zips_bipolarmin3phasecorr -- -e FLYWHEEL_API_KEY=${FLYWHEEL_API_KEY}
#
#flyw gear config --new
#flyw gear config --input input_file=test/input/subject0/5-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip --input input_file_opt=test/input/subject0/6-CLARITI_NACC263709_MR_CLARiTI_Axial_3D_ME_T2_GRE_\(MSV24\).zip -c bipolar_complex_fit=1 -c phase_corr=1 -c debug_mode=1
#flyw gear run --prepare -d src/flywheel/test/output/local_run_2_zips_bipolarmin3phasecorrdebug
#flyw gear run src/flywheel/test/output/local_run_2_zips_bipolarmin3phasecorrdebug -- -e FLYWHEEL_API_KEY=${FLYWHEEL_API_KEY}


# If gear is successful and ready to upload, run the following command:
# flyw gear upload