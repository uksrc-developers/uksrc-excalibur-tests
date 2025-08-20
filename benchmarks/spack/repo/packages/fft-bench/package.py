# from spack_repo.builtin.build_systems.generic import Package
from spack.package import *

class FftBench(CMakePackage):
    homepage = "https://github.com/Marcus-Keil/FFT_Benchmark"
    url = "https://github.com/Marcus-Keil/FFT_Benchmark/archive/refs/tags/0.3.tar.gz"

    maintainers("Marcus-Keil")

    version("0.3", sha256="dfccfb12d6d320c3838076fbb6e29498e781274b3944e042af30450c35c1e5e2")

    variant("fftw", default=True, description="FFT Benchmark Base")
    #    variant("mkl", default=False, description="Enable Intel MKL for FFTW.")
    variant("cuda", default=False, description="Enable cuFFT Library.")
    variant("rocm", default=False, description="Enable rocFFT Library.")

    depends_on("cmake@3.18:", type="build")
    depends_on("openmpi", type="build")
    depends_on("fftw")
    #    depends_on("mkl", when="+mkl")
    depends_on("cuda", when="+cuda")
    depends_on("rocfft", when="+rocm")
    depends_on("hip", when="+rocm")
    #depends_on("rocm-cmake", when="+rocm", type="build")

    # Make the backends mutually exclusive if the project can't build both
    conflicts("+cuda", when="+rocm", msg="CUDA and ROCm backends are mutually exclusive")

    def cmake_args(self):
        args = [
            self.define("BUILD_SHARED_LIBS", True),
            self.define("CMAKE_CXX_FLAGS", "-fopenmp"),
            self.define("CMAKE_EXE_LINKER_FLAGS", "-fopenmp"),
            self.define("FFTW3_DIR", self.spec['fftw'].prefix)
        ]

        if self.spec.satisfies("+cuda"):
            #            args.append(self.define("CMAKE_CXX_COMPILER", join_path(self.spec["llvm"].prefix.bin, "clang++")))
            args.append(self.define_from_variant("CUDA_FFT", "cuda"))
            args.append(self.define("CUDA_DIR", self.spec["cuda"].prefix))

        if self.spec.satisfies("+rocm"):
            # If the project *requires* the hip compiler driver, set it here.
            # Otherwise, prefer Spack's cxx wrapper and just pass HIP/ROCM dirs.
            hipcc = join_path(self.spec["hip"].prefix.bin, "hipcc")
            args.append(self.define("CMAKE_CXX_COMPILER", hipcc))
            args.append(self.define_from_variant("ROC_FFT", "rocm"))
            args.append(self.define("ROCM_DIR", self.spec["rocfft"].prefix))
            args.append(self.define("HIP_DIR", self.spec["hip"].prefix))
        #        else:
        #            args.append(self.define("CMAKE_CXX_COMPILER", join_path(self.spec["llvm"].prefix.bin, "clang++")))
        return args

    def install(self, spec, prefix):
        mkdirp(prefix)
        mkdirp(prefix.bin)

        with working_dir(self.build_directory):
            install("FFT_Bench", prefix.bin)