function [iField,voxel_size,matrix_size,CF,delta_TE,TE,B0_dir,B0_mag,phase_encoding_dir]=load_nifti_folder(path_work,load_negate_every_other_axis)

    function result=negate_every_other_axis(data_3d,axis)
        result=data_3d;
        if strcmp(axis,'row')
            result(2:2:end,:,:) = result(2:2:end,:,:)*-1;
        elseif strcmp(axis,'col')
            result(:,2:2:end,:) = result(:,2:2:end,:)*-1;
        elseif strcmp(axis,'slice')
            result(:,:,2:2:end) = result(:,:,2:2:end)*-1;
        else
            error("ERROR: Invalid value for axis - " + axis)
        end
    end

    cd([path_work '/temp_dcm2niix'])
    CF=[];
    delta_TE=[];
    TE=[];
    B0_dir=[];
    B0_mag=[];
    magnitude=[];
    phase=[];
    voxel_size=[];
    phase_encoding_dir='';
    load_negate_every_other=0;

    meta_data = jsondecode(fileread('meta_data.json'));
    inputFolder=[path_work '/temp_dcm2niix/'];
    QSMPrefix=meta_data.common_prefix;
    is_single_file=meta_data.single_file;
    numEchoes=meta_data.num_echoes;

    if meta_data.real_exists == 0 | meta_data.imaginary_exists == 0
        combine_real_imag = 0;
        if meta_data.phase_exists == 0
            error('ERROR: Cannot process because phase is missing and cannot be calculated from missing either real or imaginary or both')
        end
    else
        combine_real_imag = 1;
    end

    if ~isempty(load_negate_every_other_axis)
        if combine_real_imag == 1
            load_negate_every_other_axis=lower(load_negate_every_other_axis);
            valid_vals = {'row','col','slice'};
            if ismember(load_negate_every_other_axis, valid_vals)
                load_negate_every_other=1;
            end
        else
            disp('WARNING: load_negate_every_other_axis works only on real and imaginary data. load_negate_every_other_axis disabled')
        end
    end

    if is_single_file == 1
        % TODO: add real and imaginary combination
        disp('INFO: load_nifti_folder.m - using magnitude and phase from single files')
        jsonFileName = strcat(inputFolder,QSMPrefix,'.json'); % filename in JSON extension
        str = fileread(jsonFileName); % dedicated for reading files as text
        data = jsondecode(str); % Using the jsondecode function to parse JSON from string

        niiFileName = strcat(inputFolder,QSMPrefix,'.nii');
        niiStruct = load_untouch_nii(niiFileName);
        echoMagnitude = single(niiStruct.img) * niiStruct.hdr.dime.scl_slope + niiStruct.hdr.dime.scl_inter;

        niiFileNamePhase = strcat(inputFolder,QSMPrefix,'_ph.nii');
        niiStructPhase = load_untouch_nii(niiFileNamePhase);
        echoPhase = single(niiStructPhase.img) * niiStructPhase.hdr.dime.scl_slope + niiStructPhase.hdr.dime.scl_inter;

        CF = data.ImagingFrequency*1e6;
        manufacturer = data.Manufacturer;
        phase_encoding_dir = data.InPlanePhaseEncodingDirectionDICOM;
        B0_mag = data.MagneticFieldStrength;
        voxel_size=[niiStruct.hdr.dime.pixdim(2),niiStruct.hdr.dime.pixdim(3),niiStruct.hdr.dime.pixdim(4)];
        matrix_size=[niiStruct.hdr.dime.dim(2),niiStruct.hdr.dime.dim(3),niiStruct.hdr.dime.dim(4)];
        affine3D=[niiStruct.hdr.hist.srow_x
            niiStruct.hdr.hist.srow_y
            niiStruct.hdr.hist.srow_z];
        affine3D=affine3D(1:3,1:3);
        voxel_size_matrix=[voxel_size(1) 0 0; 0 voxel_size(2) 0; 0 0 voxel_size(3)];
        B0_dir=affine3D/voxel_size_matrix\[0 0 1]';

        orig_dim5=niiStruct.hdr.dime.dim(5);
        orig_dim1=niiStruct.hdr.dime.dim(1);
        niiStruct.hdr.dime.dim(1)=3;
        niiStruct.hdr.dime.dim(5)=1;

        magnitude=echoMagnitude;
        phase=echoPhase;
    else
        for echo = 1:numEchoes
            if combine_real_imag == 1
                disp('INFO: load_nifti_folder.m - using real and imaginary from multiple echo files')
                jsonFileName = strcat(inputFolder,QSMPrefix,int2str(echo),'_real.json'); % filename in JSON extension
                str = fileread(jsonFileName); % dedicated for reading files as text
                data = jsondecode(str); % Using the jsondecode function to parse JSON from string
                TE = [TE data.EchoTime];

                niiFileName = strcat(inputFolder,QSMPrefix,int2str(echo),'_real.nii');
                niiStruct = load_untouch_nii(niiFileName);

                niiFileNameImag = strcat(inputFolder,QSMPrefix,int2str(echo),'_imaginary.nii');
                niiStructImag = load_untouch_nii(niiFileNameImag);

                echoReal = single(niiStruct.img) * niiStruct.hdr.dime.scl_slope + niiStruct.hdr.dime.scl_inter;
                echoImag = single(niiStructImag.img) * niiStructImag.hdr.dime.scl_slope + niiStructImag.hdr.dime.scl_inter;
%                % for debug
%                disp('real (slope and inter)')
%                disp(niiStruct.hdr.dime.scl_slope)
%                disp(niiStruct.hdr.dime.scl_inter)
%                disp('imaginary (slope and inter)')
%                disp(niiStructImag.hdr.dime.scl_slope)
%                disp(niiStructImag.hdr.dime.scl_inter)
%                disp('end')
%                disp(max(max(max(echoReal))))
%                disp(max(max(max(echoImag))))
                if load_negate_every_other == 1
                    echoReal=negate_every_other_axis(echoReal,load_negate_every_other_axis);
                    echoImag=negate_every_other_axis(echoImag,load_negate_every_other_axis);
                end

                echoMagnitude = sqrt(echoReal.^2+echoImag.^2);
                echoPhase = atan2(echoImag,echoReal);
                clear echoReal echoImag
            else
                disp('INFO: load_nifti_folder.m - using magnitude and phase from multiple echo files')
                jsonFileName = strcat(inputFolder,QSMPrefix,int2str(echo),'.json'); % filename in JSON extension
                str = fileread(jsonFileName); % dedicated for reading files as text
                data = jsondecode(str); % Using the jsondecode function to parse JSON from string
                TE = [TE data.EchoTime];

                niiFileName = strcat(inputFolder,QSMPrefix,int2str(echo),'.nii');
                niiStruct = load_untouch_nii(niiFileName);
                echoMagnitude = single(niiStruct.img) * niiStruct.hdr.dime.scl_slope + niiStruct.hdr.dime.scl_inter;

                niiFileNamePhase = strcat(inputFolder,QSMPrefix,int2str(echo),'_ph.nii');
                niiStructPhase = load_untouch_nii(niiFileNamePhase);
                echoPhase = single(niiStructPhase.img) * niiStructPhase.hdr.dime.scl_slope + niiStructPhase.hdr.dime.scl_inter;
            end

            if echo == 1
                CF = data.ImagingFrequency*1e6;
                manufacturer = data.Manufacturer;
                B0_mag = data.MagneticFieldStrength;
                phase_encoding_dir = data.InPlanePhaseEncodingDirectionDICOM;
                voxel_size=[niiStruct.hdr.dime.pixdim(2),niiStruct.hdr.dime.pixdim(3),niiStruct.hdr.dime.pixdim(4)];
                matrix_size=[niiStruct.hdr.dime.dim(2),niiStruct.hdr.dime.dim(3),niiStruct.hdr.dime.dim(4)];
                magnitude=single(zeros([matrix_size, numEchoes]));
                phase=single(zeros([matrix_size, numEchoes]));
                affine3D=[niiStruct.hdr.hist.srow_x
                    niiStruct.hdr.hist.srow_y
                    niiStruct.hdr.hist.srow_z];
                affine3D=affine3D(1:3,1:3);
                voxel_size_matrix=[voxel_size(1) 0 0; 0 voxel_size(2) 0; 0 0 voxel_size(3)];
                B0_dir=affine3D/voxel_size_matrix\[0 0 1]';
            end

            magnitude(:,:,:,echo)=echoMagnitude;
            phase(:,:,:,echo)=echoPhase;
        end
        if numEchoes > 1
            delta_TE = TE(2)-TE(1);
        end
    end

    clear echoMagnitude echoPhase niiStructPhase
    if isempty(phase_encoding_dir)
        disp('WARNING: phase_encoding_dir not found')
    end

    if combine_real_imag == 0
        % when combining mag and phase to complex, phase needs to be negated
        phase = phase*-1;
    end

    if combine_real_imag == 0 & contains(manufacturer, 'siemens', 'IgnoreCase',true)
        phase=phase/4096*pi;
    end

    iField=magnitude.*exp(1i.*phase);

    disp('Finished loading nifti data')
end
