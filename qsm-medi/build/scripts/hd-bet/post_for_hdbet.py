# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

import nibabel
import os

output_folder = os.environ['OUTPUT_FOLDER']
mni_img = nibabel.load(f'{output_folder}/temp_hd-bet_output_pre_mask.nii.gz') #hd-bet always outputs .nii.gz
nat_img = nibabel.load(f'{output_folder}/temp_iMag.nii')

start_axcodes=nibabel.orientations.aff2axcodes(aff=mni_img.affine)
end_axcodes=nibabel.orientations.aff2axcodes(aff=nat_img.affine)
start_ornt=nibabel.orientations.axcodes2ornt(start_axcodes)
end_ornt=nibabel.orientations.axcodes2ornt(end_axcodes)

transform=nibabel.orientations.ornt_transform(start_ornt, end_ornt)

nat_mask_img=mni_img.as_reoriented(transform)
nibabel.save(nat_mask_img, f'{output_folder}/QSM_mask.nii')