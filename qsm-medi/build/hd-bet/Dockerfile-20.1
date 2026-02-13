FROM nvidia/cuda:10.1-runtime-ubuntu16.04

RUN apt-get update -qq \
    && apt-get install -y -q --no-install-recommends \
           apt-utils \
           curl \
           gzip \
           unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV CONDA_DIR="/opt/miniconda-latest" \
    PATH="/opt/miniconda3/bin:$PATH"
RUN conda_installer="/tmp/miniconda.sh" \
    && curl -fsSL -o "$conda_installer" https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && bash "$conda_installer" -b -p /opt/miniconda3 \
    && rm -f "$conda_installer" \
    && conda update -yq -nbase conda \
    && conda config --system --prepend channels conda-forge \
    && conda config --system --set auto_update_conda false \
    && conda config --system --set show_channel_urls true \
    && sync \
    && conda create -yq -n hd-bet \
    && bash -c ". activate hd-bet \
    &&   pip install --no-cache-dir  \
             nibabel numpy torch scikit-image SimpleITK" \
    && rm -rf ~/.cache/pip/* \
    && sync && conda clean -at && sync

COPY ["HD-BET", "/opt"]

ENV ENTRYPT="/tmp/start.sh"
RUN cd /opt/HD-BET && pip install -e . \
    && echo '#!/usr/bin/env bash' >> $ENTRYPT \
    && echo 'set -e' >> $ENTRYPT \
    && echo 'export USER="${USER:=`whoami`}"' >> $ENTRYPT \
    && echo 'if [ $# -eq 1 ]; then' >> $ENTRYPT \
    && echo '  hd-bet -i /input/$1.nii.gz' >> $ENTRYPT \
    && echo 'else hd-bet -h;echo "Usage: hd-bet -i /input/\$scanKey.nii.gz";fi' >> $ENTRYPT \
    && chmod u+x $ENTRYPT

ENTRYPOINT ["/tmp/start.sh"]
