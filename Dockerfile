# Use the official Python base image for x86_64
FROM --platform=linux/x86_64 python:3.11

# Download QEMU for cross-compilation
ADD https://github.com/multiarch/qemu-user-static/releases/download/v6.1.0-8/qemu-x86_64-static /usr/bin/qemu-x86_64-static
RUN chmod +x /usr/bin/qemu-x86_64-static

# Install required dependencies for FSL and Freesurfer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    git \
    tcsh \
    xfonts-base \
    gfortran \
    libjpeg62 \
    libtiff5-dev \
    libpng-dev \
    unzip \
    libxext6 \
    libx11-6 \
    libxmu6 \
    libglib2.0-0 \
    libxft2 \
    libxrender1 \
    libxt6 \
    ffmpeg \
    libsm6

# Install Freesurfer
ENV FREESURFER_HOME="/opt/freesurfer" \
    PATH="/opt/freesurfer/bin:$PATH" \
    FREESURFER_VERSION=7.4.1

# copy over local freesurfer binaries
RUN mkdir /freesurfer_binaries
COPY freesurfer_binaries/freesurfer-linux-centos7_x86_64-${FREESURFER_VERSION}.tar.gz /freesurfer_binaries/

ARG USE_LOCAL_FREESURFER
RUN echo USE_LOCAL_FREESURFER=${USE_LOCAL_FREESURFER}

RUN if [ "$USE_LOCAL_FREESURFER" = "True" ]; then \
      echo "Using local freesurfer binaries."; \
      tar xzC /opt -f /freesurfer_binaries/freesurfer-linux-centos7_x86_64-${FREESURFER_VERSION}.tar.gz && \
      echo ". /opt/freesurfer/SetUpFreeSurfer.sh" >> ~/.bashrc; \
    fi && \
    if [ "$USE_LOCAL_FREESURFER" = "False" ]; then \
      echo "Using freesurfer binaries from surfer.nmr.mgh.harvard.edu."; \
      curl -L --progress-bar https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/${FREESURFER_VERSION}/freesurfer-linux-centos7_x86_64-${FREESURFER_VERSION}.tar.gz | tar xzC /opt && \
      echo ". /opt/freesurfer/SetUpFreeSurfer.sh" >> ~/.bashrc; \
    fi

RUN rm -rf /freesurfer_binaries

# set bash as default terminal
SHELL ["/bin/bash", "-ce"]


ARG uid
ARG gid
# create directories for mounting input, output and project volumes
RUN mkdir -p /input /output /petdeface && \ 
    if [[ uid && gid ]] chown -R ${uid}:${gid} /input /output /petdeface


ENV PATH="/root/.local/bin:$PATH"
# setup fs env
ENV PATH=/opt/freesurfer/bin:/opt/freesurfer/fsfast/bin:/opt/freesurfer/tktools:/opt/freesurfer/mni/bin:${PATH} \
    OS=Linux \
    FREESURFER_HOME=/opt/freesurfer \
    FREESURFER=/opt/freesurfer \
    SUBJECTS_DIR=/opt/freesurfer/subjects \
    LOCAL_DIR=/opt/freesurfer/local \
    FSFAST_HOME=/opt/freesurfer/fsfast \
    FMRI_ANALYSIS_DIR=/opt/freesurfer/fsfast \
    FUNCTIONALS_DIR=/opt/freesurfer/sessions \
    FS_OVERRIDE=0 \
    FIX_VERTEX_AREA="" \
    FSF_OUTPUT_FORMAT=nii.gz \
    MINC_BIN_DIR=/opt/freesurfer/mni/bin \
    MINC_LIB_DIR=/opt/freesurfer/mni/lib \
    MNI_DIR=/opt/freesurfer/mni \
    MNI_DATAPATH=/opt/freesurfer/mni/data \
    MNI_PERL5LIB=/opt/freesurfer/mni/share/perl5 \
    PERL5LIB=/opt/freesurfer/mni/share/perl5

# copy the project
COPY . /petdeface

# install dependencies
RUN pip3 install --upgrade pip && cd /petdeface && pip3 install -e .

# set the entrypoint to the main executable petdeface.py
# we don't run petdeface.py directly because we need to set up the ownership of the output files
# so we run a wrapper script that sets up the launches petdeface.py and sets the ownership of the output files
# on successful exit or on failure using trap.
ENTRYPOINT ["bash", "/petdeface/docker_deface.sh", "python3", "/petdeface/petdeface/petdeface.py"]
