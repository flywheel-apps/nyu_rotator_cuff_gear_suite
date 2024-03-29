# Dockerfile exported by GearBuilderGUI.Stash edits before export again

# Inheriting from established docker image:
FROM ubuntu:21.10

# Inheriting from established docker image:
LABEL maintainer="Flywheel <support@flywheel.io>"

# Install APT dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-pip \
    python3-setuptools && \ 
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install PIP Dependencies
COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip && \ 
    pip3 install -r requirements.txt && \ 
    rm -rf /root/.cache/pip

# Specify ENV Variables
ENV \ 
    PATH=$PATH  \ 
    LD_LIBRARY_PATH=$LD_LIBRARY_PATH \
    FLYWHEEL_SDK_REQUEST_TIMEOUT=600

# Make directory for flywheel spec (v0):
ENV FLYWHEEL /flywheel/v0
WORKDIR ${FLYWHEEL}

# Copy executable/manifest to Gear
COPY run.py ${FLYWHEEL}/run.py
COPY utils ${FLYWHEEL}/utils
COPY manifest.json ${FLYWHEEL}/manifest.json
COPY ohif_config.json ${FLYWHEEL}/ohif_config.json

RUN chmod a+x ${FLYWHEEL}/run.py

# ENV preservation for Flywheel Engine
RUN python3 -c 'import os, json; f = open("/tmp/gear_environ.json", "w");json.dump(dict(os.environ), f)'

# Configure entrypoint
ENTRYPOINT ["/flywheel/v0/run.py"]
