function process_QSM(processing_mode,path_parameters_json,path_work)
    % QSM reconstruction pipeline
    % Please cite the publications below if this code is used
    % mSMV
    % doi: 10.1002/mrm.29963
    % ...
    % Alexandra G. Roberts
    % Cornell MRI Lab
    % 08/12/2025

    % Modified for containerization and nifti saving by Arnold Evia, Rush Alzheimer's Disease Center, 10/23/2025
    cd(path_work)
    path_ref_nii=[path_work '/temp_reference_3d.nii'];
%    path_parameters_json="/input/parameters/qsm_parameters.json";

    % Load Field(s) from dicom
%    [iField,voxel_size,matrix_size,CF,delta_TE,TE,B0_dir,B0_mag,files]=Read_DICOM('/input/dicom_data');

    % Setup pipeline parameters (will overwrite fields from dicom/nifti if field exists in json file)
    [CF_json,delta_TE_json,TE_json,B0_dir_json,B0_mag_json,pdf_tol,pdf_n_cg,pdf_space,pdf_n_pad,csf_flag_erode,csf_thresh_R2s, ...
    medi_tol_norm_ratio,medi_max_iter,medi_cg_verbose,medi_cg_max_iter,medi_cg_tol,medi_lambda,medi_msmv, ...
    load_nifti_common_prefix, load_negate_every_other_axis,phase_corr, invert_phase,phase_encoding_dir_json, ...
    method_phase_unwrap,prefilter] = load_pipeline_parameters(path_parameters_json);
    json_params = struct("CF",CF_json,"delta_TE",delta_TE_json,"TE",TE_json,"B0_dir",B0_dir_json,"B0_mag",B0_mag_json,"phase_encoding_dir",phase_encoding_dir_json);

    [iField,voxel_size,matrix_size,CF_nifti,delta_TE_nifti,TE_nifti,B0_dir_nifti,B0_mag_nifti,phase_encoding_dir_nifti]=load_nifti_folder(path_work,load_negate_every_other_axis);
    nifti_params = struct("CF",CF_nifti,"delta_TE",delta_TE_nifti,"TE",TE_nifti,"B0_dir",B0_dir_nifti,"B0_mag",B0_mag_nifti,"phase_encoding_dir",phase_encoding_dir_nifti);

    matrix_size_4d = size(iField);
    [CF,delta_TE,TE,B0_dir,B0_mag,phase_encoding_dir]=check_and_finalize_pipeline_parameters(json_params,nifti_params,matrix_size_4d,phase_corr);

    % Reference nifti structure for saving nifti files (has header information about native space)
    ref_nii_struct = load_untouch_nii(path_ref_nii);
    ref_nii_struct.hdr.dime.datatype=16;
    ref_nii_struct.hdr.dime.bitpix=32;
    ref_nii_struct.hdr.dime.scl_inter=0;
    ref_nii_struct.hdr.dime.scl_slope=1;

    if strcmp(processing_mode,'pre_hdbet')
        iMag = squeeze(sqrt(sum(abs(iField).^2,4)));
        ref_nii_struct.img=iMag;
        save_untouch_nii(ref_nii_struct,[path_work '/temp_iMag.nii']);
        return;
    end

    if invert_phase == 1
        iField = conj(iField);
    end

%    B0_mag = round(B0_mag);

    % Combined magnitude
    iMag = squeeze(sqrt(sum(abs(iField).^2,4)));

    % Mask from hdbet (will prioritize custom QSM mask)
    path_mask=[path_work '/QSM_mask.nii'];
    if isfile('/input/custom/QSM_mask.nii')
        path_mask='/input/custom/QSM_mask.nii';
        disp('INFO: Loaded custom/QSM_mask.nii')
    end
    mask_struct = load_untouch_nii(path_mask);
    Mask = single(mask_struct.img);

    noise_level = calfieldnoise(iField, Mask);
    iField = iField/noise_level; % normalizing by noise level handles very large values for real and imaginary domains; without normalizing, local field calculation may fail

    if phase_corr == 1
        [iField] = iField_correction(iField,voxel_size,Mask,phase_encoding_dir);
    else
        disp("INFO: Skipped Phase Correction")
    end

    % Nonlinear fitting, doi: 10.1002/mrm.24272
    [iFreq_raw,N_std] = Fit_ppm_complex(iField);
    ref_nii_struct.img=iFreq_raw;
    save_untouch_nii(ref_nii_struct,[path_work '/temp_iFreq_raw.nii']);

    if strcmp(method_phase_unwrap,'romeo')
        % ROMEO phase unwrapping, 10.1002/mrm.28563
        iFreq = romeo(iFreq_raw, iMag, single(Mask));
        ref_nii_struct.img=iFreq;
        save_untouch_nii(ref_nii_struct,[path_work '/temp_iFreq.nii']);
    elseif strcmp(method_phase_unwrap,'laplacian')
        iFreq = unwrapLaplacian(iFreq_raw, matrix_size, voxel_size);
        ref_nii_struct.img=iFreq;
        save_untouch_nii(ref_nii_struct,[path_work '/temp_iFreq_laplacian.nii']);
    end

    % PDF background field removal, doi: 10.1002/nbm.1670
    [RDF,shim] = PDF(iFreq,N_std,Mask,matrix_size,voxel_size,B0_dir,pdf_tol,pdf_n_cg,pdf_space,pdf_n_pad);
    ref_nii_struct.img=RDF;
    save_untouch_nii(ref_nii_struct,[path_work '/temp_RDF.nii']);

    % ARLO R2s fitting, doi: 10.1002/mrm.25137
    R2s = arlo(TE,abs(iField));
    ref_nii_struct.img=R2s;
    save_untouch_nii(ref_nii_struct,[path_work '/temp_R2s.nii']);

    % Homogeneity mask, doi: 10.1111/jon.12923
    if isfile('/input/custom/Mask_CSF.nii')
        mask_struct = load_untouch_nii('/input/custom/Mask_CSF.nii');
        Mask_CSF = single(mask_struct.img);
    else
        Mask_CSF = extract_all_CSF(R2s,Mask,voxel_size,csf_flag_erode,csf_thresh_R2s);
        ref_nii_struct.img=Mask_CSF;
        save_untouch_nii(ref_nii_struct,[path_work '/temp_Mask_CSF.nii']);
    end

    output_both_prefilter_options=0;
    if prefilter == 2
        output_both_prefilter_options=1;
        prefilter = -1;
    end

    % mSMV parameter, doi: 10.1002/mrm.29963
    % Use prefilter = 1 for a constant kernel of specified by `radius`
%    prefilter = -1;
    save_msmv = 1;
    % Save variables needed for dipole inversion

    cd(path_work)
    save RDFv.mat RDF iFreq iFreq_raw iMag N_std Mask matrix_size voxel_size delta_TE CF B0_dir Mask_CSF R2s B0_mag prefilter save_msmv -v7.3;

    % MEDI reconstruction, doi: 10.1016/j.neuroimage.2011.08.082
    QSM = MEDI_L1('filename', 'RDFv.mat', 'lambda', medi_lambda, 'merit', 'msmv', medi_msmv,'tol_norm_ratio',medi_tol_norm_ratio,'max_iter',medi_max_iter,'cg_verbose',medi_cg_verbose,'cg_max_iter',medi_cg_max_iter,'cg_tol',medi_cg_tol);
    if ismember('RDF_msmv', who('-file', 'RDFv.mat'))
        ref_nii_struct.img = getfield(load('RDFv.mat', 'RDF_msmv'), 'RDF_msmv');
        save_untouch_nii(ref_nii_struct,[path_work '/temp_RDF_msmv.nii']);
    end
    ref_nii_struct.img=QSM;
    save_untouch_nii(ref_nii_struct,[path_work '/QSM.nii']);

    if output_both_prefilter_options == 1
        prefilter = 1;
        save RDFprefilter1.mat RDF iFreq iFreq_raw iMag N_std Mask matrix_size voxel_size delta_TE CF B0_dir Mask_CSF R2s B0_mag prefilter save_msmv -v7.3;

        QSM = MEDI_L1('filename', 'RDFprefilter1.mat', 'lambda', medi_lambda, 'merit', 'msmv', medi_msmv,'tol_norm_ratio',medi_tol_norm_ratio,'max_iter',medi_max_iter,'cg_verbose',medi_cg_verbose,'cg_max_iter',medi_cg_max_iter,'cg_tol',medi_cg_tol);
        if ismember('RDF_msmv', who('-file', 'RDFprefilter1.mat'))
            ref_nii_struct.img = getfield(load('RDFprefilter1.mat', 'RDF_msmv'), 'RDF_msmv');
            save_untouch_nii(ref_nii_struct,[path_work '/temp_RDF_msmv_prefilter1.nii']);
        end
        ref_nii_struct.img=QSM;
        save_untouch_nii(ref_nii_struct,[path_work '/QSM_prefilter1.nii']);
        delete([path_work '/RDFprefilter1.mat']);
    end
