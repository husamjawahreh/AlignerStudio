# syntax=docker/dockerfile:1.7
# Research-only ToothInstanceNet runtime.
# Build with the exact cached source staged into the temporary build context;
# no GitHub clone occurs.
FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TORCH_CUDA_ARCH_LIST="7.5;8.0;8.6;8.9;9.0"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-dev python3.12-venv python3-pip \
    build-essential git cmake ninja-build libegl1-mesa-dev libgl1-mesa-dev \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.12 /usr/local/bin/python

WORKDIR /opt/alignerstudio
COPY source /opt/3dteethland/
COPY research/benchmark/toothinstancenet/runtime/requirements-runtime.txt /opt/alignerstudio/requirements-runtime.txt

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --index-url https://download.pytorch.org/whl/cu128 \
        torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 \
    && python -m pip install -r /opt/alignerstudio/requirements-runtime.txt \
    && python -m pip install --no-build-isolation --no-binary=torch-scatter torch-scatter==2.1.2 \
    && python -m pip install -v -e /opt/3dteethland

COPY research/benchmark/toothinstancenet/runtime/runtime-manifest.py /opt/alignerstudio/runtime-manifest.py
COPY research/benchmark/toothinstancenet/run_acceptance.py /opt/alignerstudio/run_acceptance.py
COPY adapters /opt/alignerstudio/adapters
COPY domain /opt/alignerstudio/domain
COPY engines /opt/alignerstudio/engines

ENV PYTHONPATH=/opt/alignerstudio \
    ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE=/opt/3dteethland

CMD ["python", "/opt/alignerstudio/run_acceptance.py"]
