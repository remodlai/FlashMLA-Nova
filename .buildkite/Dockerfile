ARG CUDA_VERSION=12.9.1
FROM nvidia/cuda:${CUDA_VERSION}-devel-ubuntu22.04 AS build

ARG PYTHON_VERSION=3.12
ARG TORCH_CUDA_ARCH_LIST

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.12 and build tools
RUN apt-get update -y \
    && apt-get install -y software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update -y \
    && apt-get install -y \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-dev \
        python${PYTHON_VERSION}-venv \
        git \
        curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

# Create virtual environment
RUN /root/.local/bin/uv venv /opt/venv --python ${PYTHON_VERSION}

ENV PATH="/opt/venv/bin:/root/.local/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# Install build dependencies
RUN uv pip install --python /opt/venv/bin/python setuptools wheel packaging

ARG PYTORCH_INDEX_URL
RUN uv pip install --python /opt/venv/bin/python torch==2.8.0 --extra-index-url ${PYTORCH_INDEX_URL}

RUN uv pip install --python /opt/venv/bin/python ninja cmake sccache

WORKDIR /workspace
COPY . .

# Build the wheel
ARG USE_SCCACHE=1
ARG SCCACHE_BUCKET
ARG SCCACHE_REGION
ARG SCCACHE_S3_NO_CREDENTIALS=1
ARG SCCACHE_IDLE_TIMEOUT=0

RUN if [ "$USE_SCCACHE" = "1" ]; then \
        export SCCACHE_BUCKET=${SCCACHE_BUCKET} \
        && export SCCACHE_REGION=${SCCACHE_REGION} \
        && export SCCACHE_S3_NO_CREDENTIALS=${SCCACHE_S3_NO_CREDENTIALS} \
        && export SCCACHE_IDLE_TIMEOUT=${SCCACHE_IDLE_TIMEOUT} \
        && sccache --show-stats \
        && python setup.py bdist_wheel --dist-dir=dist \
        && sccache --show-stats; \
    else \
        python setup.py bdist_wheel --dist-dir=dist; \
    fi

