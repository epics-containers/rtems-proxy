# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION} as developer

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv-proxy
ENV PATH=/venv-proxy/bin:$PATH

# The build stage installs the context into the venv
FROM developer as build
COPY . /context
WORKDIR /context
RUN pip install .

# additional packages
RUN pip install -r requirements.txt

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim as runtime

COPY --from=build /venv-proxy/ /venv-proxy/
ENV PATH=/venv-proxy/bin:$PATH

# change this entrypoint if it is not the same as the repo
ENTRYPOINT ["rtems-proxy"]
CMD ["--version"]
