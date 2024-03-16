ARG PYTHON_VERSION=3.12.2
FROM python:${PYTHON_VERSION}-alpine3.19

# add bash as epics-container scripts require it
RUN apk update && \
    apk upgrade && \
    apk add bash

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

#
COPY . /context
WORKDIR /context
RUN pip install .
# additional packages
RUN pip install -r requirements.txt

ENTRYPOINT ["rtems-proxy"]
CMD ["--version"]
