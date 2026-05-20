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
    [imaging_frequency_json,delta_TE_json,TE_json,B0_dir_json,B0_mag_json,pdf_tol,pdf_n_cg,pdf_space,pdf_n_pad,csf_flag_erode,csf_thresh_R2s, ...
    medi_tol_norm_ratio,medi_max_iter,medi_cg_verbose,medi_cg_max_iter,medi_cg_tol,medi_lambda,medi_msmv, ...
    load_nifti_common_prefix, load_negate_every_other_axis,phase_corr, invert_phase,phase_encoding_dir_json, ...
    method_phase_unwrap,prefilter, bipolar_complex_fit,debug_mode] = load_pipeline_parameters(path_parameters_json);
    json_params = struct("delta_TE",delta_TE_json,"TE",TE_json,"B0_dir",B0_dir_json,"B0_mag",B0_mag_json,"phase_encoding_dir",phase_encoding_dir_json);

    [iField,raw_magnitude,raw_phase,voxel_size,matrix_size,CF,delta_TE_nifti,TE_nifti,B0_dir_nifti,B0_mag_nifti,phase_encoding_dir_nifti]=load_nifti_folder(path_work,load_negate_every_other_axis,imaging_frequency_json);
    nifti_params = struct("CF",CF,"delta_TE",delta_TE_nifti,"TE",TE_nifti,"B0_dir",B0_dir_nifti,"B0_mag",B0_mag_nifti,"phase_encoding_dir",phase_encoding_dir_nifti);

    matrix_size_4d = size(iField);
    [delta_TE,TE,B0_dir,B0_mag,phase_encoding_dir]=check_and_finalize_pipeline_parameters(json_params,nifti_params,matrix_size_4d,phase_corr);

    if isempty(phase_encoding_dir)
        phase_corr=0;
        disp("INFO: Phase correction not used because phase_encoding_dir was not set")
    end

    % Reference nifti structure for saving nifti files (has header information about native space)
    ref_nii_struct = load_untouch_nii(path_ref_nii);
    ref_nii_struct.hdr.dime.datatype=16;
    ref_nii_struct.hdr.dime.bitpix=32;
    ref_nii_struct.hdr.dime.scl_inter=0;
    ref_nii_struct.hdr.dime.scl_slope=1;

    if strcmp(processing_mode,'pre_hdbet')
        iMag = squeeze(sqrt(sum(abs(iField).^2,4)));
        ref_nii_struct.img=iMag;
        save_untouch_nii(ref_nii_struct,[path_work '/iMag.nii']);
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
        if bipolar_complex_fit == 1
            iField_odd = iField(:,:,:,1:2:end);
            iField_even = iField(:,:,:,2:2:end);
            [iField_odd] = iField_correction(iField_odd,voxel_size,Mask,phase_encoding_dir);
            [iField_even] = iField_correction(iField_even,voxel_size,Mask,phase_encoding_dir);
            iField(:,:,:,1:2:end) = iField_odd;
            iField(:,:,:,2:2:end) = iField_even;
            clear iField_odd iField_even
        else
            [iField] = iField_correction(iField,voxel_size,Mask,phase_encoding_dir);
        end
    else
        disp("INFO: Skipped Phase Correction")
    end

    num_echoes=size(raw_phase,4);
    ref_nii_struct.hdr.dime.dim(1)=4;
    ref_nii_struct.hdr.dime.dim(5)=num_echoes;
    ref_nii_struct.img=raw_phase;
    save_untouch_nii(ref_nii_struct,[path_work '/raw_phase.nii']);
    ref_nii_struct.img=raw_magnitude;
    save_untouch_nii(ref_nii_struct,[path_work '/raw_magnitude.nii']);
    clear raw_phase raw_magnitude
    if debug_mode == 1
        ref_nii_struct.img=angle(iField);
        save_untouch_nii(ref_nii_struct,[path_work '/temp_phase_prior_to_fit.nii']);
        ref_nii_struct.img=abs(iField);
        save_untouch_nii(ref_nii_struct,[path_work '/temp_magnitude_prior_to_fit.nii']);
    end
    ref_nii_struct.hdr.dime.dim(1)=3;
    ref_nii_struct.hdr.dime.dim(5)=1;
    
    if bipolar_complex_fit == 1
        % Nonlinear fitting, doi: 10.1002/mrm.24272
        % Bipolar fit is over a longer effective echo time that needs to be
        % corrected [iFreq = (1/2)*romeo(2*iFreq_raw, iMag, single(Mask)]
        [iFreq_raw,N_std,rel_res,iFreq_0,iFreq_0e] = Fit_ppm_complex_bipolar(iField);
        iFreq_raw=iFreq_raw*2;
        ref_nii_struct.img=iFreq_0e;
        save_untouch_nii(ref_nii_struct,[path_work '/temp_iFreq_0e.nii']);
        clear iFreq_0e
    else
        % Nonlinear fitting, doi: 10.1002/mrm.24272
        [iFreq_raw,N_std,rel_res,iFreq_0] = Fit_ppm_complex(iField);
    end
    ref_nii_struct.img=rel_res;
    save_untouch_nii(ref_nii_struct,[path_work '/temp_iFreq_rel_res.nii']);
    ref_nii_struct.img=iFreq_raw;
    save_untouch_nii(ref_nii_struct,[path_work '/iFreq_raw.nii']);
    ref_nii_struct.img=iFreq_0;
    save_untouch_nii(ref_nii_struct,[path_work '/temp_iFreq_0.nii']);
    clear iFreq_0 rel_res

    if strcmp(method_phase_unwrap,'romeo')
        % ROMEO phase unwrapping, 10.1002/mrm.28563
        if bipolar_complex_fit == 1
            iFreq = (1/2)*romeo(iFreq_raw, iMag, single(Mask));
        else
            iFreq = romeo(iFreq_raw, iMag, single(Mask));
        end
        
        ref_nii_struct.img=iFreq;
        save_untouch_nii(ref_nii_struct,[path_work '/iFreq.nii']);
    elseif strcmp(method_phase_unwrap,'laplacian')
        iFreq = unwrapLaplacian(iFreq_raw, matrix_size, voxel_size);
        ref_nii_struct.img=iFreq;
        save_untouch_nii(ref_nii_struct,[path_work '/iFreq_laplacian.nii']);
    end

    % PDF background field removal, doi: 10.1002/nbm.1670
    [RDF,shim] = PDF(iFreq,N_std,Mask,matrix_size,voxel_size,B0_dir,pdf_tol,pdf_n_cg,pdf_space,pdf_n_pad);
    ref_nii_struct.img=RDF;
    save_untouch_nii(ref_nii_struct,[path_work '/RDF.nii']);

    % ARLO R2s fitting, doi: 10.1002/mrm.25137
    R2s = arlo(TE,abs(iField));
    ref_nii_struct.img=R2s;
    save_untouch_nii(ref_nii_struct,[path_work '/R2s.nii']);

    % Homogeneity mask, doi: 10.1111/jon.12923
    if isfile('/input/custom/Mask_CSF.nii')
        mask_struct = load_untouch_nii('/input/custom/Mask_CSF.nii');
        Mask_CSF = single(mask_struct.img);
    else
        Mask_CSF = extract_all_CSF(R2s,Mask,voxel_size,csf_flag_erode,csf_thresh_R2s);
        ref_nii_struct.img=Mask_CSF;
        save_untouch_nii(ref_nii_struct,[path_work '/Mask_CSF.nii']);
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
    save temp_RDFv.mat RDF iFreq iFreq_raw iMag N_std Mask matrix_size voxel_size delta_TE CF B0_dir Mask_CSF R2s B0_mag prefilter save_msmv -v7.3;

    % MEDI reconstruction, doi: 10.1016/j.neuroimage.2011.08.082
    QSM = MEDI_L1('filename', 'temp_RDFv.mat', 'lambda', medi_lambda, 'merit', 'msmv', medi_msmv,'tol_norm_ratio',medi_tol_norm_ratio,'max_iter',medi_max_iter,'cg_verbose',medi_cg_verbose,'cg_max_iter',medi_cg_max_iter,'cg_tol',medi_cg_tol);
    if ismember('RDF_msmv', who('-file', 'temp_RDFv.mat'))
        ref_nii_struct.img = getfield(load('temp_RDFv.mat', 'RDF_msmv'), 'RDF_msmv');
        save_untouch_nii(ref_nii_struct,[path_work '/RDF_msmv.nii']);
    end
    ref_nii_struct.img=QSM;
    save_untouch_nii(ref_nii_struct,[path_work '/QSM.nii']);

    if output_both_prefilter_options == 1
        prefilter = 1;
        save temp_RDFprefilter1.mat RDF iFreq iFreq_raw iMag N_std Mask matrix_size voxel_size delta_TE CF B0_dir Mask_CSF R2s B0_mag prefilter save_msmv -v7.3;

        QSM = MEDI_L1('filename', 'temp_RDFprefilter1.mat', 'lambda', medi_lambda, 'merit', 'msmv', medi_msmv,'tol_norm_ratio',medi_tol_norm_ratio,'max_iter',medi_max_iter,'cg_verbose',medi_cg_verbose,'cg_max_iter',medi_cg_max_iter,'cg_tol',medi_cg_tol);
        if ismember('RDF_msmv', who('-file', 'temp_RDFprefilter1.mat'))
            ref_nii_struct.img = getfield(load('temp_RDFprefilter1.mat', 'RDF_msmv'), 'RDF_msmv');
            save_untouch_nii(ref_nii_struct,[path_work '/RDF_msmv_prefilter1.nii']);
        end
        ref_nii_struct.img=QSM;
        save_untouch_nii(ref_nii_struct,[path_work '/QSM_prefilter1.nii']);
    end

    if debug_mode == 0
        cd(path_work)
        rmdir('temp_dcm2niix', 's')
        rmdir('results', 's')
        delete('temp_*')
    end
    