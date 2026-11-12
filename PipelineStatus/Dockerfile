FROM python:3.11-slim

# Flywheel runs gears from /flywheel/v0 and reads the manifest from there.
ENV FLYWHEEL=/flywheel/v0
WORKDIR $FLYWHEEL

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY manifest.json PipeLineStatus.py ./

# No ENTRYPOINT: Flywheel starts the gear with the manifest's "command".
# Manager.conf is not baked into the image so no API key ever ships with it;
# for a local (non-gear) run, mount it in and run from its folder:
#   docker run --rm -v "$PWD":/work -w /work pipeline-status:0.1.0 \
#       python /flywheel/v0/PipeLineStatus.py
