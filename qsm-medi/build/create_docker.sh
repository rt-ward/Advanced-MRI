# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

docker_repo="aevia.azurecr.io"
docker_img_tag="qsm-medi:2.2.0"

docker run --rm repronim/neurodocker:0.9.5 generate docker \
  -b ubuntu:18.04 \
  -p apt \
  --matlabmcr version=2018b \
  --miniconda version=py38_23.5.2-0 pip_install='nibabel==5.1.0' \
  --copy hd-bet/HD-BET/ /opt/HD-BET --workdir /opt/HD-BET --run "pip install -e ." \
  --dcm2niix version=7d295ff5e9f4b31227b9ef4c89e0118ddef457a6 method=source \
  --copy matlab_compiler/pipeline_qsm_v1.1.0 /opt/process_QSM \
  --copy scripts /opt/process_QSM \
  --entrypoint='/opt/process_QSM/run.sh' > Dockerfile

# https://repo.continuum.io blocked on Rush network
sed -i 's\https://repo.continuum.io\https://repo.anaconda.com\g' Dockerfile

echo "RUN pip install flywheel-sdk" >> Dockerfile
echo 'COPY ["flywheel/run.py", "/opt/process_QSM/flywheel/run.py"]' >> Dockerfile

docker build -t ${docker_repo}/${docker_img_tag} .
#docker push ${docker_repo}/${docker_img_tag}