function [CF,delta_TE,TE,B0_dir,B0_mag,phase_encoding_dir]=check_and_finalize_pipeline_parameters(json_params,nifti_params,matrix_size,phase_corr)
    format long
    num_errors_encountered = 0;

    function result = TEs_have_even_echo_spacing(TEs_in)
        % Needs at least 3 TEs to continue
        if length(TEs_in) < 3
            result = 0;
            return;
        end

        tol=10^-4;
        temp_diff_TEs = diff(TEs_in);
        % Check if the difference of differences is less than the tolerance of 0.0001
        result=all(abs(diff(temp_diff_TEs)) < tol);
    end

    for param = ["CF","delta_TE","TE","B0_dir","B0_mag","phase_encoding_dir"]
        if isempty(json_params.(param))
            pipeline_params.(param) = nifti_params.(param);
        else
            pipeline_params.(param) = json_params.(param);
        end
    end
    CF=pipeline_params.CF;
    delta_TE=pipeline_params.delta_TE;
    TE=pipeline_params.TE;
    B0_dir=pipeline_params.B0_dir;
    B0_mag=pipeline_params.B0_mag;
    phase_encoding_dir=pipeline_params.phase_encoding_dir;

    %% Sanity checks
    if length(matrix_size) ~= 4
        num_errors_encountered = num_errors_encountered + 1;
        disp("ERROR: Input data is not 4 dimensional. matrix_size = " + matrix_size)
    else
        if matrix_size(4) ~= length(TE)
            num_errors_encountered = num_errors_encountered + 1;
            disp("ERROR: Fourth dimension of input data does not match the number of TEs")
        end
    end

    % Checks on TE
    num_TEs = length(TE);
    if num_TEs > 1 % is multi echo
        if num_TEs == 2
            delta_TE = TE(2) - TE(1);
            disp("INFO: Passed sanity checks on TE")
            disp(TE)
        else
            diff_TEs = diff(TE);
            if TEs_have_even_echo_spacing(TE)
                if delta_TE ~= diff_TEs(1)
                    disp("WARNING: delta_TE does not match the difference in TEs. Changing delta_TE to match difference in TE")
                    delta_TE = diff_TEs(1);
                end
                disp("INFO: Passed sanity checks on TE")
                disp(TE)
            else
                num_errors_encountered = num_errors_encountered + 1;
                disp("ERROR: TE list has uneven echo spacing")
                TE
                diff_TE=diff(TE)
            end
        end
    elseif num_TEs == 1
        num_errors_encountered = num_errors_encountered + 1;
        disp("ERROR: Pipeline only supports multi-echo data")
    end

    % Checks on required parameters
    if isempty(CF)
        num_errors_encountered = num_errors_encountered + 1;
        disp("ERROR: Pipeline parameter CF is empty. Please provide ImagingFrequency in config file")
    end
    if isempty(delta_TE)
        num_errors_encountered = num_errors_encountered + 1;
        disp("ERROR: Pipeline parameter delta_TE is empty. Please provide delta_TE in config file")
    end
    if isempty(TE)
        num_errors_encountered = num_errors_encountered + 1;
        disp("ERROR: Pipeline parameter TE list is empty. Please provide TE in config file")
    end
    if isempty(B0_dir)
        num_errors_encountered = num_errors_encountered + 1;
        disp("ERROR: Pipeline parameter B0_dir is empty. Please provide B0_dir in config file")
    end
    if isempty(B0_mag)
        num_errors_encountered = num_errors_encountered + 1;
        disp("ERROR: Pipeline parameter B0_mag is empty. Please provide B0_mag in config file")
    end

    if phase_corr == 1 & isempty(phase_encoding_dir)
        disp('WARNING: phase_encoding_dir was not found in imaging data or provided by user. Removal of the echo-dependent linear phase will be applied to both in-plane axes');
    end

    if num_errors_encountered > 0
        error('ERROR: Pipeline cannot continue until json parameter errrors are resolved')
    end
end

