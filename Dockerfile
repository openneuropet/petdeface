# docker build for distributing a base fs 7.3.0 container
FROM --platform=linux/amd64 martinnoergaard/petprep_hmc

# set bash as default terminal
SHELL ["/bin/bash", "-ce"]

# shell settings
WORKDIR /root

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

ENTRYPOINT ["/usr/bin/env"]
CMD ["python3", "/project/petdeface/petdeface.py"]

