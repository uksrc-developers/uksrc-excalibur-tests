#from spack_repo.builtin.build_systems.generic import Package
from spack.package import *
import os

class FftBench(CMakePackage):
    homepage = "https://github.com/Marcus-Keil/FFT_Benchmark"
    url = "https://github.com/Marcus-Keil/FFT_Benchmark/archive/refs/tags/0.3.tar.gz"

    maintainers("Marcus-Keil")

    version("0.3", sha256="586e26570a6a927a54b7163d11ec7cfe7306c140fd7ad7b401e26948b28530dc")

    variant("fftw", default=True, description="FFT Benchmark Base")
#    variant("mkl", default=False, description="Enable Intel MKL for FFTW.")
    variant("cuda", default=False, description="Enable cuFFT Library.")
    variant("rocm", default=False, description="Enable rocFFT Library.")

    depends_on("fftw", type="link")
#    depends_on("mkl", when="+mkl", type="link")
    depends_on("cuda", when="+cuda", type="link")
    depends_on("rocm", when="+rocm", type="link")
    depends_on("hip", when="+rocm", type="link")
    depends_on("rocfft", when="+rocm", type="link")

    conflicts("+cuda", when="+rocm", msg="CUDA and ROCm support are mutually exclusive.")

    def cmake_args(self):
        print(self.spec["fftw"].prefix)
        args = [
            "-DFFTW3_DIR={0}".format(self.spec['fftw'].prefix),
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
                self.define("ROCM_DIR", self.spec["rocfft"].prefix),
                self.define("HIP_DIR", self.spec["hip"].prefix),
#                "-DROCM_DIR={}".format(self.spec['rocm'].prefix),
#                "-DHIP_DIR={}".format(self.spec['hip'].prefix)
            ])
        return args

    def install(self, spec, prefix):
        exe_path = join_path(self.build_directory, "fft-bench")
        if not os.path.isfile(exe_path):
            raise FileNotFoundError(f"Expected binary not found: {exe_path}")
        mkdirp(prefix.bin)
        install(exe_path, prefix.bin)

#    def install(self, spec, prefix):
#    #    src = (os.getcwd()[:os.getcwd().rfind("/")] +
#    #           "/spack-build-" +
#    #           str(spec)[str(spec).find("/")+1:str(spec).find("/")+8] +
#    #           "/FFT_Bench")
#    #    install_path = prefix + "/bin"
#    #    mkdir(install_path)
#        cmake()
#        build()
#        install(src, install_path)
