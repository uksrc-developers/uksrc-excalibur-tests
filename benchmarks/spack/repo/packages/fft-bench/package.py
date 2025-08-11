from spack_repo.builtin.build_systems.generic import Package
from spack.package import *
import os

class FftBench(CMakePackage):
    homepag = "https://github.com/Marcus-Keil/FFT_Benchmark"
    url = "https://github.com/Marcus-Keil/FFT_Benchmark/archive/refs/tags/0.2.tar.gz"

    maintainers("Marcus-Keil")

    version("0.3", sha256="586e26570a6a927a54b7163d11ec7cfe7306c140fd7ad7b401e26948b28530dc")

    variant("fftw", default=True, description="FFT Benchmark Base")
    depends_on("fftw", type="link")

#    variant("mkl", default=False, description="Enable Intel MKL for FFTW.")
#    depends_on("mkl", when="+mkl", type="link")

    variant("cuda", default=False, description="Enable cuFFT Library.")
    depends_on("cuda", when="+cuda", type="link")

    variant("rocm", default=False, description="Enable rocFFT Library.")
    depends_on("rocm", when="+rocm", type="link")
    depends_on("hip", when="+rocm", type="link")

    depends_on("c", type="build")
    depends_on("cxx", type="build", when="-rocm")
    depends_on("hipcc", type="build", when="+rocm")

    def cmake_args(self):
        print(self.spec["fftw"].prefix)
        args = [
            self.define("CMAKE_EXE_LINKER_FLAGS", "-fopenmp"),
            "-DFFTW3_DIR={0}".format(self.spec['fftw'].prefix),
            self.define_from_variant("ONEAPI", "mkl")
        ]
#        if "+mkl" in self.spec:
#            args.extend([
#                self.define_from_variant("ONEAPI", "mkl"),
#                "-DONEAPI_DIR={0}".format(self.spec['mkl'].prefix)
#            ])
        if "+cuda" in self.spec:
            args.extend([
                self.define_from_variant("CUDA_FFT", "cuda"),
                "-DCUDA_DIR={0}".format(self.spec['cuda'].prefix)
            ])
        if "+rocm" in self.spec:
            args.extend([
                self.define_from_variant("ROC_FFT", "rocm"),
                "-DROCM_DIR={}".format(self.spec['rocm'].prefix),
                "-DHIP_DIR={}".format(self.spec['hip'].prefix)
            ])
        
        return args

    def install(self, spec, prefix):
    #    src = (os.getcwd()[:os.getcwd().rfind("/")] +
    #           "/spack-build-" +
    #           str(spec)[str(spec).find("/")+1:str(spec).find("/")+8] +
    #           "/FFT_Bench")
    #    install_path = prefix + "/bin"
    #    mkdir(install_path)
        cmake()
        build()
        install(src, install_path)
