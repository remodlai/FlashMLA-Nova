import os
from pathlib import Path
from datetime import datetime
import subprocess

from setuptools import setup, find_packages

from torch.utils.cpp_extension import (
    BuildExtension,
    CUDAExtension,
    IS_WINDOWS,
    CUDA_HOME
)


def is_flag_set(flag: str) -> bool:
    return os.getenv(flag, "FALSE").lower() in ["true", "1", "y", "yes"]

def get_features_args():
    features_args = []
    if is_flag_set("FLASH_MLA_DISABLE_FP16"):
        features_args.append("-DFLASH_MLA_DISABLE_FP16")
    return features_args

def get_arch_flags():
    # Check NVCC Version
    # NOTE The "CUDA_HOME" here is not necessarily from the `CUDA_HOME` environment variable. For more details, see `torch/utils/cpp_extension.py`
    assert CUDA_HOME is not None, "PyTorch must be compiled with CUDA support"
    nvcc_version = subprocess.check_output(
        [os.path.join(CUDA_HOME, "bin", "nvcc"), '--version'], stderr=subprocess.STDOUT
    ).decode('utf-8')
    nvcc_version_number = nvcc_version.split('release ')[1].split(',')[0].strip()
    major, minor = map(int, nvcc_version_number.split('.'))
    print(f'Compiling using NVCC {major}.{minor}')

    DISABLE_SM100 = is_flag_set("FLASH_MLA_DISABLE_SM100")
    DISABLE_SM90 = is_flag_set("FLASH_MLA_DISABLE_SM90")
    if major < 12 or (major == 12 and minor <= 8):
        assert DISABLE_SM100, "sm100 compilation for Flash MLA requires NVCC 12.9 or higher. Please set FLASH_MLA_DISABLE_SM100=1 to disable sm100 compilation, or update your environment."

    arch_flags = []
    if not DISABLE_SM100:
        arch_flags.extend(["-gencode", "arch=compute_100a,code=sm_100a"])
    if not DISABLE_SM90:
        arch_flags.extend(["-gencode", "arch=compute_90a,code=sm_90a"])
    return arch_flags

def get_nvcc_thread_args():
    nvcc_threads = os.getenv("NVCC_THREADS") or "32"
    return ["--threads", nvcc_threads]

subprocess.run(["git", "submodule", "update", "--init", "csrc/cutlass"])

this_dir = os.path.dirname(os.path.abspath(__file__))

if IS_WINDOWS:
    cxx_args = ["/O2", "/std:c++17", "/DNDEBUG", "/W0"]
else:
    cxx_args = ["-O3", "-std=c++17", "-DNDEBUG", "-Wno-deprecated-declarations"]

ext_modules = []

# Base source files (always included)
sources = [
    "csrc/pybind.cpp",
    "csrc/smxx/get_mla_metadata.cu",
    "csrc/smxx/mla_combine.cu",
]

# Add SM90 sources if not disabled
DISABLE_SM90 = is_flag_set("FLASH_MLA_DISABLE_SM90")
if not DISABLE_SM90:
    sources.extend([
        "csrc/sm90/decode/dense/splitkv_mla.cu",
        "csrc/sm90/decode/sparse_fp8/splitkv_mla.cu",
        "csrc/sm90/prefill/sparse/fwd.cu",
    ])

# Add SM100 sources if not disabled
DISABLE_SM100 = is_flag_set("FLASH_MLA_DISABLE_SM100")
if not DISABLE_SM100:
    sources.extend([
        "csrc/sm100/decode/sparse_fp8/splitkv_mla.cu",
        "csrc/sm100/prefill/dense/fmha_cutlass_fwd_sm100.cu",
        "csrc/sm100/prefill/dense/fmha_cutlass_bwd_sm100.cu",
        "csrc/sm100/prefill/sparse/fwd.cu",
    ])

ext_modules.append(
    CUDAExtension(
        name="flash_mla.cuda",
        sources=sources,
        extra_compile_args={
            "cxx": cxx_args + get_features_args() + ["-DNO_PYBIND11=1"],
            "nvcc": [
                "-O3",
                "-std=c++17",
                "-DNDEBUG",
                "-D_USE_MATH_DEFINES",
                "-Wno-deprecated-declarations",
                "-U__CUDA_NO_HALF_OPERATORS__",
                "-U__CUDA_NO_HALF_CONVERSIONS__",
                "-U__CUDA_NO_HALF2_OPERATORS__",
                "-U__CUDA_NO_BFLOAT16_CONVERSIONS__",
                "--expt-relaxed-constexpr",
                "--expt-extended-lambda",
                "--use_fast_math",
                "--ptxas-options=-v,--register-usage-level=10",
                "-DNO_PYBIND11=1"
            ] + get_features_args() + get_arch_flags() + get_nvcc_thread_args(),
        },
        include_dirs=[
            Path(this_dir) / "csrc",
            Path(this_dir) / "csrc" / "sm90",
            Path(this_dir) / "csrc" / "cutlass" / "include",
            Path(this_dir) / "csrc" / "cutlass" / "tools" / "util" / "include",
        ],
    )
)

ext_modules.append(
    CUDAExtension(
        name="flash_mla.dense_fp8",
        sources=[
            "csrc/extension/sm90/dense_fp8/pybind.cpp",
            "csrc/extension/sm90/dense_fp8/flash_fwd_mla_fp8_sm90.cu",
        ],
        extra_compile_args={
            "cxx": cxx_args + get_features_args() + ["-DNO_PYBIND11=1"],
            "nvcc": [
                "-O3",
                "-std=c++17",
                "-DNDEBUG",
                "-D_USE_MATH_DEFINES",
                "-Wno-deprecated-declarations",
                "-U__CUDA_NO_HALF_OPERATORS__",
                "-U__CUDA_NO_HALF_CONVERSIONS__",
                "-U__CUDA_NO_HALF2_OPERATORS__",
                "-U__CUDA_NO_BFLOAT16_CONVERSIONS__",
                "--expt-relaxed-constexpr",
                "--expt-extended-lambda",
                "--use_fast_math",
                "--ptxas-options=-v,--register-usage-level=10",
                "-DNO_PYBIND11=1"
            ] + get_features_args() + get_arch_flags() + get_nvcc_thread_args(),
        },
        include_dirs=[
            Path(this_dir) / "csrc",
            Path(this_dir) / "csrc" / "sm90",
            Path(this_dir) / "csrc" / "extension" / "sm90" / "dense_fp8",
            Path(this_dir) / "csrc" / "cutlass" / "include",
            Path(this_dir) / "csrc" / "cutlass" / "tools" / "util" / "include",
        ],
    )
)

try:
    cmd = ['git', 'rev-parse', '--short', 'HEAD']
    git_commit = subprocess.check_output(cmd).decode('ascii').rstrip()
except Exception as _:
    git_commit = None

# Get CUDA version from nvcc
cuda_version = "unknown"
if CUDA_HOME:
    try:
        nvcc_output = subprocess.check_output(
            [os.path.join(CUDA_HOME, "bin", "nvcc"), '--version'],
            stderr=subprocess.STDOUT
        ).decode('utf-8')
        version_str = nvcc_output.split('release ')[1].split(',')[0].strip()
        major, minor = version_str.split('.')[:2]
        cuda_version = f"cu{major}{minor}"
    except:
        pass

# Build version string: 1.0.0+cu129.git_commit
if git_commit:
    version_suffix = f"+{cuda_version}.{git_commit}"
else:
    now = datetime.now()
    date_time_str = now.strftime("%Y%m%d%H%M%S")
    version_suffix = f"+{cuda_version}.{date_time_str}"

setup(
    name="flash_mla",
    version="1.0.0" + version_suffix,
    packages=find_packages(include=['flash_mla']),
    ext_modules=ext_modules,
    cmdclass={"build_ext": BuildExtension},
)

