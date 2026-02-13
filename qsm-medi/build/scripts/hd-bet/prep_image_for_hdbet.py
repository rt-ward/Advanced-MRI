# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

import nibabel
import os

output_folder = os.environ['OUTPUT_FOLDER']
img = nibabel.load(f'{output_folder}/temp_iMag.nii')
data = img.get_fdata()


img=nibabel.nifti1.Nifti1Image(data,img.affine,header=img.header)
#https://nipy.org/nibabel/reference/nibabel.orientations.html
curr_ax=nibabel.orientations.aff2axcodes(aff=img.affine)
MNI = (('R','L'),('P','A'),('I','S'))
transform=nibabel.orientations.axcodes2ornt(curr_ax,MNI)

img=img.as_reoriented(transform)
nibabel.save(img, f'{output_folder}/temp_hd-bet_input.nii.gz')
