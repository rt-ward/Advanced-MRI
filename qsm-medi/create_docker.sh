# SPDX-FileCopyrightText: 2025 Arnold Evia <Arnold_Evia@rush.edu>
#
# SPDX-License-Identifier: BSD-3-Clause

docker_repo="aevia.azurecr.io"
docker_img_tag="qsm-medi:2.4.1"

docker run --rm repronim/neurodocker:0.9.5 generate docker \
  -b ubuntu:18.04 \
  -p apt \
  --matlabmcr version=2018b \
  --run "curl -LsSf https://astral.sh/uv/install.sh | sh" \
  --run "mkdir -p /opt/uv/cache" --env UV_CACHE_DIR="/opt/uv/cache" \
  --copy pyproject.toml /opt/process_QSM/pyproject.toml --copy .python-version /opt/process_QSM/.python-version \
  --workdir /opt/process_QSM --env PATH='/opt/process_QSM/.venv/bin:/root/.local/bin:$PATH' --run "uv sync --no-dev" \
  --copy src/hd-bet/HD-BET/ /opt/HD-BET --run "uv pip install /opt/HD-BET" \
  --dcm2niix version=7d295ff5e9f4b31227b9ef4c89e0118ddef457a6 method=source \
  --copy src/matlab_compiler/pipeline_qsm_v1.3.0 /opt/process_QSM \
  --copy src/scripts /opt/process_QSM \
  --copy src/config /config \
  --copy src/flywheel/run.py /opt/process_QSM/flywheel/run.py \
  --entrypoint='/opt/process_QSM/run.sh' > Dockerfile

# https://repo.continuum.io blocked on Rush network
#sed -i 's\https://repo.continuum.io\https://repo.anaconda.com\g' Dockerfile
#
#echo "RUN uv pip install flywheel-sdk" >> Dockerfile
#echo 'COPY ["src/flywheel/run.py", "/opt/process_QSM/flywheel/run.py"]' >> Dockerfile

docker build -t ${docker_repo}/${docker_img_tag} --progress=plain .
docker push ${docker_repo}/${docker_img_tag}