# This container is bases on epics-base so that we have access to the msi tool
# and CA client tools for diagnostics.
FROM ghcr.io/epics-containers/epics-base-developer:7.0.10ec1 AS developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    rsync \
    telnet \
    && apt-get dist-clean

# The build stage installs the context into the venv
FROM developer AS build

# Change the working directory to the `app` directory
# and copy in the project
WORKDIR /app
COPY . /app
RUN chmod o+wrX .

# Tell uv sync to install python in a known location so we can copy it out later
ENV UV_PYTHON_INSTALL_DIR=/python

# Sync the project without its dev dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev

ENV PATH=/app/.venv/bin:$PATH

# Create directories for hybrid mode compatibility in devcontainers
RUN mkdir -p /epics/ioc /epics/runtime /ioc_tftp /ioc_nfsv2

# The runtime stage copies the built venv into a runtime container
FROM ghcr.io/epics-containers/epics-base-runtime:7.0.10ec1 AS runtime

# Add apt-get system dependencies for runtime here if needed
# RUN apt-get update -y && apt-get install -y --no-install-recommends \
#     some-library \
#     && apt-get dist-clean

# Copy the python installation from the build stage
COPY --from=build /python /python

# Copy the environment, but not the source code
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH


# change this entrypoint if it is not the same as the repo
ENTRYPOINT ["rtems-proxy"]
CMD ["--version"]
