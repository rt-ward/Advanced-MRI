# ---------------------------------------------------------------------------
# Flywheel gear for mri_reface 0.3.5, built on the official NITRC Docker image.
#
# The base image comes from mri_reface_0.3.5_docker.zip on NITRC and is named
# "mri_reface" locally. Tag it first so this build is pinned:
#     docker tag mri_reface:latest mri_reface:0.3.5
# ---------------------------------------------------------------------------
FROM mri_reface:0.3.5

# The mri_reface image runs as a non-root user whose home holds the MATLAB
# Runtime cache. Override at build time if `docker inspect` shows otherwise.
ARG REFACE_USER=reface-user

USER root

ENV FLYWHEEL=/flywheel/v0
RUN mkdir -p ${FLYWHEEL}/input ${FLYWHEEL}/output ${FLYWHEEL}/work
WORKDIR ${FLYWHEEL}

# run.py needs python3 (standard library only). No-op if already present.
RUN if ! command -v python3 >/dev/null 2>&1; then \
      if command -v apt-get >/dev/null 2>&1; then \
        apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*; \
      elif command -v dnf >/dev/null 2>&1; then \
        dnf install -y python3 && dnf clean all; \
      elif command -v yum >/dev/null 2>&1; then \
        yum install -y python3 && yum clean all; \
      elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache python3; \
      else \
        echo "No python3 and no known package manager" && exit 1; \
      fi; \
    fi

COPY manifest.json run.py ${FLYWHEEL}/
RUN chmod 755 ${FLYWHEEL}/run.py \
 && chown -R ${REFACE_USER} ${FLYWHEEL} \
 && chmod -R a+rwX ${FLYWHEEL}

# Run as the same user mri_reface was built for (MATLAB Runtime cache lives
# in its home directory).
USER ${REFACE_USER}

# Flywheel runs the manifest "command"; clear any entrypoint inherited from
# the base image so it isn't swallowed as arguments.
ENTRYPOINT []
CMD []
