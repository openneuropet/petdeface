# docker build for distributing a base fs 7.3.0 container
FROM --platform=linux/amd64 quay.io/centos/centos:stream8

# set bash as default terminal
SHELL ["/bin/bash", "-ce"]

# shell settings
WORKDIR /root

# install utils
RUN yum -y update && \
    yum -y install bc libgomp perl tar tcsh wget vim-common && \
    yum -y install mesa-libGL libXext libSM libXrender libXmu gcc-gfortran && \
    dnf groupinstall 'development tools' -y && \
    dnf install openssl-devel bzip2-devel libffi-devel -y && \
    yum clean all

# install fs
RUN wget --progress=bar:force:noscroll https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.3.0/freesurfer-linux-centos8_x86_64-7.3.0.tar.gz -O fs.tar.gz && \
    tar --no-same-owner -xzvf fs.tar.gz && \
    mv freesurfer /usr/local && \
    rm fs.tar.gz

# install python
RUN curl https://www.python.org/ftp/python/3.9.1/Python-3.9.1.tgz -O \
    && tar -xzf Python-3.9.1.tgz \
    && cd Python-3.9.1 \
    && yum -y install sqlite-devel sqlite \
    && ./configure --enable-optimizations --enable-loadable-sqlite-extensions \
    && make install

# create directories for mounting input, output and project volumes
RUN mkdir -p /input /output /project/petdeface

# install poetry and insert poetry into bash rc
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    echo export PATH="/root/.local/bin:$PATH" >> ~/.bashrc && \
    export PATH="/root/.local/bin:$PATH" && \
    /bin/bash -c "source ~/.bashrc"

ENV PATH="/root/.local/bin:$PATH"

# copy poetry.lock and pyproject.toml
COPY poetry.lock pyproject.toml /project/

# convert poetry.lock to requirements.txt and install dependencies
RUN cd /project && \
    poetry export -f requirements.txt > requirements.txt && \
    pip3 install -r /project/requirements.txt

# copy the rest of the project
COPY ./petdeface /project/petdeface

# install fsl
COPY fslinstaller.py /
RUN python3 /fslinstaller.py

# setup fs env
ENV PATH="/usr/local/freesurfer/bin:/usr/local/freesurfer/fsfast/bin:/usr/local/freesurfer/tktools:/usr/local/freesurfer/mni/bin:$PATH" \
    OS=Linux \
    FREESURFER_HOME=/usr/local/freesurfer \
    FREESURFER=/usr/local/freesurfer \
    SUBJECTS_DIR=/usr/local/freesurfer/subjects \
    LOCAL_DIR=/usr/local/freesurfer/local \
    FSFAST_HOME=/usr/local/freesurfer/fsfast \
    FMRI_ANALYSIS_DIR=/usr/local/freesurfer/fsfast \
    FUNCTIONALS_DIR=/usr/local/freesurfer/sessions \
    FS_OVERRIDE=0 \
    FIX_VERTEX_AREA="" \
    FSF_OUTPUT_FORMAT=nii.gz \
    MINC_BIN_DIR=/usr/local/freesurfer/mni/bin \
    MINC_LIB_DIR=/usr/local/freesurfer/mni/lib \
    MNI_DIR=/usr/local/freesurfer/mni \
    MNI_DATAPATH=/usr/local/freesurfer/mni/data \
    MNI_PERL5LIB=/usr/local/freesurfer/mni/share/perl5 \
    PERL5LIB=/usr/local/freesurfer/mni/share/perl5
