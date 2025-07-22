import os
import sys
import reframe as rfm
import reframe.utility.sanity as sn

from benchmarks.modules.utils import SpackTest


class FfftBenmchmarkBase(SpackTest):
    # Systems and programming environments where to run this benchmark.
    # Systems/partitions can be identified by their features, `+feature` is a
    # partition which has the named feature, `-feature` is a partition which
    # does not have the named feature.  This is a CPU-only benchmark, so we use
    # `-gpu` to exclude GPU partitions.
    valid_systems = ['*']
    valid_prog_environs = ['default']
    tasks = parameter([1])
    num_tasks_per_node = 1
    cpus_per_task = parameter([16])
    sourcesdir = os.path.dirname(__file__)
    time_limit = '1h'

    executable = 'FFT_Bench'

    reference = {
        'myriad': {
            'Libarary': ("FFTW", None, None, None),
            'Size': (1., None, None, 'MB'),
            'Time': (1., None, None, 'miliseconds'),
        }
    }

    @run_before('run')
    def replace_launcher(self):
        self.job.launcher = getlauncher('local')()

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        # Tags are useful for categorizing tests and quickly selecting those of interest.
        # self.tags.add("fftw")
        # With `env_vars` you can set environment variables to be used in the
        # job.  For example with `OMP_NUM_THREADS` we set the number of OpenMP
        # threads (not actually used in this specific benchmark).  Note that
        # this has to be done after setup because we need to add entries to
        # ReFrame built-in `env_vars` variable.
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

    @sanity_function
    def validate(self):
        return sn.assert_found(r'Run_Finished', self.stdout)

    # A performance benchmark.
    @run_before('performance')
    def set_perf_patterns(self):
        self.perf_patterns = {
            dict(
                sn.extractall(
                    r'<Library>,\t\t<Size>,\t\t<Time>,',
                    self.stdout, ['Library', 'Size', 'Time'], [str, float, float])
            )
        }

@rfm.simple_test
class FftBenchmarkCPU(FfftBenmchmarkBase):
    valid_systems = ['-gpu']
    spack_spec = 'fft-bench@0.2.b +fftw'

    # Arguments to pass to the program above to run the benchmarks.
    # -s float = Starting memory footprint in MB
    # -m int = Number of runs to do after starting memory footprint
    # -n int = Number of times to repeat a run for averaging
    # -f Run with FFTW3 Library
    # -c Run with CUDA Library
    # -r Run with RocFFT Library
    executable_opts = ["-s", "500", "-m", "0", "-n", "1", "-f"]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("fftw")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

@rfm.simple_test
class FftBenchmarkMKL(FfftBenmchmarkBase):
    valid_systems = ['-gpu']
    spack_spec = 'fft-bench@0.2 +mkl'

    # Arguments to pass to the program above to run the benchmarks.
    # -s float = Starting memory footprint in MB
    # -m int = Number of runs to do after starting memory footprint
    # -n int = Number of times to repeat a run for averaging
    # -f Run with FFTW3 Library
    # -c Run with CUDA Library
    # -r Run with RocFFT Library
    executable_opts = ["-s", "500", "-m", "0", "-n", "1", "-f"]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("mkl")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

@rfm.simple_test
class FftBenchmarkCUDA(FfftBenmchmarkBase):
    valid_systems = ['+cuda']
    spack_spec = 'fft-bench@0.2.b +cuda'

    # Arguments to pass to the program above to run the benchmarks.
    # -s float = Starting memory footprint in MB
    # -m int = Number of runs to do after starting memory footprint
    # -n int = Number of times to repeat a run for averaging
    # -f Run with FFTW3 Library
    # -c Run with CUDA Library
    # -r Run with RocFFT Library
    executable_opts = ["-s", "500", "-m", "0", "-n", "1", "-f", "-c"]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("fftw+cuda")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

@rfm.simple_test
class FftBenchmarkCUDA(FfftBenmchmarkBase):
    valid_systems = ['+gpu']
    spack_spec = 'fft-bench@0.2.b +rocfft'

    # Arguments to pass to the program above to run the benchmarks.
    # -s float = Starting memory footprint in MB
    # -m int = Number of runs to do after starting memory footprint
    # -n int = Number of times to repeat a run for averaging
    # -f Run with FFTW3 Library
    # -c Run with CUDA Library
    # -r Run with RocFFT Library
    executable_opts = ["-s", "500", "-m", "0", "-n", "1", "-f", "-r"]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("fftw+rocfft")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'