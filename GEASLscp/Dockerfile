ARG TARGETARCH
# Base image pinned by digest for reproducibility (ubuntu:22.04 as of review).
FROM --platform=linux/amd64 ubuntu:22.04@sha256:281c5745f657873d78e5531fc5ba8575f46ab7769b94550ac99543f122679986

# Set environment variables
ENV DEBIAN_FRONTEND="noninteractive" \
    LANG="en_US.UTF-8" \
    FLYWHEEL=/flywheel/v0 \
    OS="Linux" \
    FS_OVERRIDE=0 \
    FIX_VERTEX_AREA="" \
    FSF_OUTPUT_FORMAT="nii.gz" \
    FREESURFER_HOME="/opt/freesurfer" \
    FSLDIR="/opt/fsl-6.0.7.1" \
    SUBJECTS_DIR="/opt/freesurfer/subjects" \
    FUNCTIONALS_DIR="/opt/freesurfer/sessions" \
    MNI_DIR="/opt/freesurfer/mni" \
    LOCAL_DIR="/opt/freesurfer/local" \
    MINC_BIN_DIR="/opt/freesurfer/mni/bin" \
    MINC_LIB_DIR="/opt/freesurfer/mni/lib" \
    MNI_DATAPATH="/opt/freesurfer/mni/data" \
    PERL5LIB="/opt/freesurfer/mni/lib/perl5/5.8.5" \
    MNI_PERL5LIB="/opt/freesurfer/mni/lib/perl5/5.8.5" \
    PATH="/opt/freesurfer/bin:/opt/freesurfer/tktools:/opt/freesurfer/mni/bin:/opt/fsl-6.0.7.1/bin:/opt/ants-2.5.4/bin:$PATH" \
    FSLOUTPUTTYPE="NIFTI_GZ" \
    FSLMULTIFILEQUIT="TRUE" \
    FSLLOCKDIR="" \
    FSLMACHINELIST="" \
    FSLREMOTECALL="" \
    FSLGECUDAQ="cuda.q" \
    MKL_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    PYTHONNOUSERSITE=1 \
    LIBOMP_USE_HIDDEN_HELPER_TASK=0 \
    LIBOMP_NUM_HIDDEN_HELPER_THREADS=0

# Create Flywheel directory
WORKDIR ${FLYWHEEL}
RUN mkdir -p ${FLYWHEEL}

# Install utilities and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bc \
    binutils \
    bsdmainutils \
    bzip2 \
    ca-certificates \
    curl \
    dc \
    dcm2niix \
    file \
    gnupg \
    jq \
    libc6-amd64-cross \
    libfontconfig1 \
    libfreetype6 \
    libgl1-mesa-dev \
    libgl1-mesa-dri \
    libglu1-mesa-dev \
    libice6 \
    libopenblas-base \
    libtinfo6 \
    libxcursor1 \
    libxft2 \
    libxinerama1 \
    libxrandr2 \
    libxrender1 \
    libxt6 \
    lsb-release \
    nano \
    netbase \
    python3 \
    python3-pip \
    unzip \
    wget \
    zip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install FreeSurfer
COPY freesurfer7.4.1-exclude.txt /usr/local/etc/freesurfer7.4.1-exclude.txt
RUN curl -sSL https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.4.1/freesurfer-linux-ubuntu22_amd64-7.4.1.tar.gz | \
    tar zxv --no-same-owner -C /opt --exclude-from=/usr/local/etc/freesurfer7.4.1-exclude.txt && \
    rm -rf /opt/freesurfer/average /opt/freesurfer/mni/data

# Install ANTs
# ANTs config
ENV ANTSPATH="/opt/ants-2.5.4/bin" \
    PATH="$ANTSPATH:$PATH"
RUN mkdir /opt/ants && \
    curl -fsSL https://github.com/ANTsX/ANTs/releases/download/v2.5.4/ants-2.5.4-ubuntu-22.04-X64-gcc.zip -o ants.zip && \
    unzip ants.zip -d /opt && \
    rm ants.zip

# Install FSL
RUN curl -fsSL https://fsl.fmrib.ox.ac.uk/fsldownloads/fslconda/releases/fslinstaller.py | \
    python3 - -d /opt/fsl-6.0.7.1 -V 6.0.7.1 && \
    rm -rf /opt/fsl-6.0.7.1/doc /opt/fsl-6.0.7.1/data

# Python dependencies, pinned to the versions validated in this image.
# numpy is pinned <2 (the pipeline requires the 1.x ABI); pinning every
# package means nothing pulls numpy 2.x back in, so no force-reinstall is
# needed.
RUN pip3 install --no-cache-dir \
    "numpy==1.26.4" \
    "scipy==1.15.3" \
    "nibabel==5.4.2" \
    "matplotlib==3.10.9" \
    "fw-gear[sdk]==0.3.7" \
    "reportlab==5.0.1" \
    "nilearn==0.14.1"
# Create a non-root user to run the gear
RUN groupadd -r flywheel && useradd -r -g flywheel -d ${FLYWHEEL} -s /bin/bash flywheel

# Copy files and give the non-root user ownership of the gear tree
COPY ./input/ ${FLYWHEEL}/input/
COPY ./workflows/ ${FLYWHEEL}/workflows/
COPY ./pipeline_singlePLD.sh ${FLYWHEEL}/
RUN chmod -R u+rwX ${FLYWHEEL} && chown -R flywheel:flywheel ${FLYWHEEL}

# Run as the non-root user
USER flywheel

# Set entrypoint
ENTRYPOINT ["/bin/bash", "/flywheel/v0/pipeline_singlePLD.sh"]
