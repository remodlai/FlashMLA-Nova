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

# Install build dependencies
ARG PYTORCH_INDEX_URL
RUN /root/.local/bin/uv pip install --system \
    torch==2.8.0 \
    --extra-index-url ${PYTORCH_INDEX_URL} \
    && /root/.local/bin/uv pip install --system ninja cmake sccache setuptools wheel packaging

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
        && python${PYTHON_VERSION} setup.py bdist_wheel --dist-dir=dist \
        && sccache --show-stats; \
    else \
        python${PYTHON_VERSION} setup.py bdist_wheel --dist-dir=dist; \
    fi

