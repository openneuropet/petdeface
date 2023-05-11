# we use Martin's container as it's already set up with freesurfer
FROM --platform=linux/amd64 martinnoergaard/petprep_hmc

# set bash as default terminal
SHELL ["/bin/bash", "-ce"]

# create directories for mounting input, output and project volumes
RUN mkdir -p /input /output /petdeface

ENV PATH="/root/.local/bin:$PATH"

# copy the project
COPY . /petdeface

RUN cd /petdeface && \
    pip3 install -e .

RUN echo ". /opt/freesurfer/SetUpFreeSurfer.sh" >> ~/.bashrc

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["./opt/freesurfer/SetUpFreeSurfer.sh"]
