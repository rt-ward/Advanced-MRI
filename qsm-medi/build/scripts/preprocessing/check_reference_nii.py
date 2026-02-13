# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

import nibabel
import os

output_folder = os.environ['OUTPUT_FOLDER']
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
