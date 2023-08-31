# Use the official Python base image for x86_64
FROM --platform=linux/x86_64 python:3.9

ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    
    # [Optional] Add sudo support. Omit if you don't need to install software after connecting.
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME


# [Optional] Set the default user. Omit if you want to keep the default as root.
ARG DEBIAN_FRONTEND=noninteractive
ARG USER=${USERNAME}

# Download QEMU for cross-compilation
ADD https://github.com/multiarch/qemu-user-static/releases/download/v6.1.0-8/qemu-x86_64-static /usr/bin/qemu-x86_64-static
RUN sudo chmod +x /usr/bin/qemu-x86_64-static

# Install required dependencies for FSL and Freesurfer
RUN DEBIAN_FRONTEND=noninteractive \
    && apt-get update \ 
    && apt-get install -y build-essential --no-install-recommends make \
        ca-certificates \
        git \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        wget \
        curl \
        llvm \
        libncurses5-dev \
        xz-utils \
        tk-dev \
        libxml2-dev \
        libxmlsec1-dev \
        libffi-dev \
        liblzma-dev \
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

RUN curl -L https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.3.2/freesurfer-linux-centos7_x86_64-7.3.2.tar.gz | tar xzC /opt && \
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


# Python and poetry installation
USER $USER
ARG HOME="/home/$USER"
ARG PYTHON_VERSION=3.10
# ARG PYTHON_VERSION=3.10

ENV PYENV_ROOT="${HOME}/.pyenv"
ENV PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${HOME}/.local/bin:$PATH"

RUN echo "done 0" \
    && curl https://pyenv.run | bash \
    && echo "done 1" \
    && pyenv install ${PYTHON_VERSION} \
    && echo "done 2" \
    && pyenv global ${PYTHON_VERSION} \
    && echo "done 3" \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && poetry config virtualenvs.in-project true

# install dependencies
#RUN pip3 install --upgrade pip

#ADD ../../pyproject.toml /petdeface/pyproject.toml

#RUN cd petdeface && pip3 install -e .

# copy the project
#COPY . /petdeface

# set the entrypoint to the main executable petdeface.py
#ENTRYPOINT ["python3", "/petdeface/petdeface/petdeface.py"]
