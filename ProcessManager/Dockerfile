# Use standard Python 3 Linux base
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

# Define standard Flywheel directory structure
ENV FLYWHEEL=/flywheel/v0
WORKDIR ${FLYWHEEL}

# install Python dependencies
COPY requirements.txt ${FLYWHEEL}/requirements.txt
RUN pip3 install --no-cache-dir -r ${FLYWHEEL}/requirements.txt

COPY run.py ${FLYWHEEL}/run.py
COPY manifest.json ${FLYWHEEL}/manifest.json
RUN chmod +x ${FLYWHEEL}/run.py

# Run as a non-root user
RUN useradd -m -s /bin/bash flywheel \
    && chown -R flywheel:flywheel ${FLYWHEEL}
USER flywheel

ENTRYPOINT ["python3", "/flywheel/v0/run.py"]
