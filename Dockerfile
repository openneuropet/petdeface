# Use the official Python base image for x86_64
FROM --platform=linux/x86_64 python:3.9

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
    libxt6

# Install Freesurfer
ENV FREESURFER_HOME="/opt/freesurfer" \
    PATH="/opt/freesurfer/bin:$PATH"

RUN curl -L --progress-bar https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.3.2/freesurfer-linux-centos7_x86_64-7.3.2.tar.gz | tar xzC /opt && \
    echo ". /opt/freesurfer/SetUpFreeSurfer.sh" >> ~/.bashrc

# set bash as default terminal
SHELL ["/bin/bash", "-ce"]

# create directories for mounting input, output and project volumes
RUN mkdir -p /input /output /petdeface

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

# install dependencies
RUN pip3 install --upgrade pip

ADD requirements.txt /petdeface/requirements.txt

RUN pip3 install -r  /petdeface/requirements.txt

# copy the project
COPY . /petdeface

# set the entrypoint to the main executable petdeface.py
ENTRYPOINT ["python3", "/petdeface/petdeface/petdeface.py", "/input", "--output_dir","/output"]
