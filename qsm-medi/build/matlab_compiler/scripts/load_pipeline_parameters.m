function [CF,delta_TE,TE,B0_dir,B0_mag,pdf_tol,pdf_n_cg,pdf_space,pdf_n_pad,csf_flag_erode,csf_thresh_R2s,medi_tol_norm_ratio,medi_max_iter,medi_cg_verbose,medi_cg_max_iter,medi_cg_tol,medi_lambda,medi_msmv,load_nifti_common_prefix,load_negate_every_other_axis,phase_corr,invert_phase,phase_encoding_dir,method_phase_unwrap,prefilter] = load_pipeline_parameters(path_parameters_json)
    % Default pipeline parameters:
    pdf_tol = 0.1; % 0.1 in PDF.m
    pdf_n_cg = 30; % 30 in PDF.m, 300 during longitudinal testing
    pdf_space= 'imagespace'; % 'imagespace' in PDF.m
    pdf_n_pad = 40; % 40 in PDF.m
    csf_flag_erode = 1; % 1 in extract_all_CSF()
    csf_thresh_R2s = 5; % 5 in extract_all_CSF()
    medi_tol_norm_ratio = 0.1; % 0.1 in parse_QSM_input()
    medi_max_iter = 10; % 10 in parse_QSM_input()
    medi_cg_verbose = 0; % 0 in parse_QSM_input()
    medi_cg_max_iter = 100; % 100 in parse_QSM_input()
    medi_cg_tol = 0.01; % 0.01 in parse_QSM_input()
    medi_lambda = 1000; % 1000 based on suggestion from AR
    medi_msmv = 5; % 5 based on suggestion from AR
    load_nifti_common_prefix = '';
    load_negate_every_other_axis = '';
    phase_corr = 1;
    invert_phase = 0;
    method_phase_unwrap = 'romeo'; % romeo or laplacian. laplacian works better with open ended fringe lines
    prefilter = -1; % -1 for variable smv, 1 for smv, 0 for RDF already processed by smv

    num_errors_encountered = 0;
    % Imaging information
    phase_encoding_dir = '';
    CF = [];
    delta_TE = [];
    TE = [];
    B0_dir = [];
    B0_mag = [];

    % Load parameters from json file, if file exists
    if isfile(path_parameters_json)
        json_data = jsondecode(fileread(path_parameters_json));

        if isfield(json_data,'ImagingFrequency')  %CF aka ImagingFrequency * 1e6
            IF = json_data.ImagingFrequency;
            disp("INFO: Loaded ImagingFrequency from json as " + IF)
            CF = IF*1e6;
            disp("INFO: Calculated CF from ImagingFrequency as " + CF)
        end
        if isfield(json_data,'delta_TE')
            delta_TE = json_data.delta_TE;
            disp("INFO: Loaded delta_TE from json as " + delta_TE)
        end
        if isfield(json_data,'TE')
            TE = json_data.TE;
            disp("INFO: Loaded TE from json as ")
            disp("  - " + TE)
        end
        if isfield(json_data,'B0_dir')
            B0_dir = json_data.B0_dir;
            disp("INFO: Loaded B0_dir from json as " + B0_dir)
        end
        if isfield(json_data,'B0_mag')
            B0_mag = json_data.B0_mag;
            disp("INFO: Loaded B0_mag from json as " + B0_mag)
        end
        if isfield(json_data,'phase_encoding_dir')
            phase_encoding_dir_pre = json_data.phase_encoding_dir;
            if strcmp(phase_encoding_dir_pre,'ROW') | strcmp(phase_encoding_dir_pre,'COL')
                phase_encoding_dir = phase_encoding_dir_pre;
                disp("INFO: Loaded phase_encoding_dir from json as " + phase_encoding_dir)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp("ERROR: phase_encoding_dir in json file must have a value of either 'ROW' or 'COL'");
            end
        end

        if isfield(json_data,'load_nifti_common_prefix')
            load_nifti_common_prefix = json_data.load_nifti_common_prefix;
            disp("INFO: Loaded load_nifti_common_prefix from json as " + load_nifti_common_prefix)
        end
        if isfield(json_data,'load_negate_every_other_axis')
            load_negate_every_other_axis = json_data.load_negate_every_other_axis;
            if strcmpi(load_negate_every_other_axis,'row') | strcmpi(load_negate_every_other_axis,'col') | strcmpi(load_negate_every_other_axis,'slice')
                disp("INFO: Loaded load_negate_every_other_axis from json as " + load_negate_every_other_axis)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp("ERROR: load_negate_every_other_axis in json file must have a value of either 'ROW', 'COL', or 'SLICE'");
            end
        end
        if isfield(json_data,'phase_corr')
            phase_corr = json_data.phase_corr;
            if phase_corr == 1 || phase_corr == 0
                disp("INFO: Loaded phase_corr from json as " + phase_corr)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp("ERROR: phase_corr in json file must have a value of either 1 or 0, (true or false, respectively)");
            end
        end
        if isfield(json_data,'invert_phase')
            invert_phase = json_data.invert_phase;
            if invert_phase == 1 || invert_phase == 0
                disp("INFO: Loaded invert_phase from json as " + invert_phase)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp("ERROR: invert_phase in json file must have a value of either 1 or 0, (true or false, respectively)");
            end
        end
        if isfield(json_data,'method_phase_unwrap')
            method_phase_unwrap = json_data.method_phase_unwrap;
            if strcmp(method_phase_unwrap,'romeo') | strcmp(method_phase_unwrap,'laplacian')
                method_phase_unwrap = method_phase_unwrap;
                disp("INFO: Loaded method_phase_unwrap from json as " + method_phase_unwrap)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp('ERROR: method_phase_unwrap in json file must have a value of either "romeo" or "laplacian"');
            end
        end
        if isfield(json_data,'prefilter')
            prefilter = json_data.prefilter;
            if prefilter == 1 || prefilter == 0 || prefilter == -1 || prefilter == 2
                disp("INFO: Loaded prefilter from json as " + prefilter)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp("ERROR: prefilter in json file must have a value of either 1, 0, or -1 (constant smv kernel, no smv prefilter, or variable smv kernel, respectively)");
            end
        end

        % PDF() options
        if isfield(json_data,'pdf_tol')
            pdf_tol = json_data.pdf_tol;
            disp("INFO: Loaded pdf_tol from json as " + pdf_tol)
        end
        if isfield(json_data,'pdf_n_cg')
            pdf_n_cg = json_data.pdf_n_cg;
            disp("INFO: Loaded pdf_n_cg from json as " + pdf_n_cg)
        end
        if isfield(json_data,'pdf_space')
            pdf_space = json_data.pdf_space;
            if strcmp(pdf_space, 'imagespace') || strcmp(pdf_space, 'kspace')
                disp("INFO: Loaded pdf_space from json as " + pdf_space)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp('ERROR: pdf_space in json file must have a value of either "imagespace" or "kspace"');
            end
        end
        if isfield(json_data,'pdf_n_pad')
            pdf_n_pad = json_data.pdf_n_pad;
            disp("INFO: Loaded pdf_n_pad from json as " + pdf_n_pad)
        end

        % extract_all_CSF() options
        if isfield(json_data,'csf_flag_erode')
            csf_flag_erode = json_data.csf_flag_erode;
            if invert_phase == 1 || invert_phase == 0
                disp("INFO: Loaded csf_flag_erode from json as " + csf_flag_erode)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp("ERROR: csf_flag_erode in json file must have a value of either 1 or 0, (true or false, respectively)");
            end
        end

        if isfield(json_data,'csf_thresh_R2s')
            csf_thresh_R2s = json_data.csf_thresh_R2s;
            disp("INFO: Loaded csf_thresh_R2s from json as " + csf_thresh_R2s)
        end

        % MEDI_L1() options
        if isfield(json_data,'medi_lambda')
            medi_lambda = json_data.medi_lambda;
            disp("INFO: Loaded medi_lambda from json as " + medi_lambda)
        end
        if isfield(json_data,'medi_msmv')
            medi_msmv = json_data.medi_msmv;
            disp("INFO: Loaded medi_msv from json as " + medi_msmv)
        end
        if isfield(json_data,'medi_tol_norm_ratio')
            medi_tol_norm_ratio = json_data.medi_tol_norm_ratio;
            disp("INFO: Loaded medi_tol_norm_ratio from json as " + medi_tol_norm_ratio)
        end
        if isfield(json_data,'medi_max_iter')
            medi_max_iter = json_data.medi_max_iter;
            disp("INFO: Loaded medi_max_iter from json as " + medi_max_iter)
        end
        if isfield(json_data,'medi_cg_verbose')
            medi_cg_verbose = json_data.medi_cg_verbose;
            disp("INFO: Loaded medi_cg_verbose from json as " + medi_cg_verbose)
        end
        if isfield(json_data,'medi_cg_max_iter')
            medi_cg_max_iter = medi_cg_max_iter;
            disp("INFO: Loaded medi_cg_max_iter from json as " + medi_cg_max_iter)
        end
        if isfield(json_data,'medi_cg_tol')
            medi_cg_tol = medi_cg_tol;
            disp("INFO: Loaded medi_cg_tol from json as " + medi_cg_tol)
        end
    end

    if num_errors_encountered > 0
        error('ERROR: Pipeline cannot continue until json parameter errrors are resolved')
    end
end