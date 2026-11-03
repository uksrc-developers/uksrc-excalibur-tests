import pathlib, os

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function

from benchmarks.modules.utils import SpackTest

NUMBER_OF_TRANSFORMS = '7'
NUMBER_OF_REPEATS = '10'

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
    #sourcesdir = os.path.dirname(__file__)
    time_limit = '2h'

    executable = 'FFT_Bench'

    reference = {
        'myriad': {
            'Libarary': ("FFTW", None, None, None),
            'Size': (1., None, None, 'MB'),
            'Time': (1., None, None, 'miliseconds'),
        }
    }

    fft_output_file = "./default.txt"

    def __init__(self):
        self.bench_name = "FFT Bench"
        self.output_dict_list = []

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
        return sn.assert_true(os.path.isfile(self.stagedir + '/' + self.fft_output_file))

    @run_before("performance")
    def output_list_dict(self):
        pattern = r'(?P<Library>\S+), (?P<Mem_Size>\S+), (?P<Avg_time>\S+),'
        output_list = sn.extractall(pattern,
                                    pathlib.Path(self.stagedir) / self.fft_output_file,
                                    ['Library', 'Mem_Size', 'Avg_time'],
                                    [str, float, float])
        time_of_test = str(dt.now().strftime("%Y-%m-%d-%H:%M"))

        for output in output_list:
            self.output_dict_list += [
                {
                    "Date": time_of_test,
                    "System - Partition": f"{self.current_system.name} - {self.current_partition.name}",
                    "Library": output[0],
                    "Array size [MB]": output[1],
                    "Avg. Time [ms]":output[2]
                }
            ]
        return

    @performance_function('s')
    def dummy_perf(self):
        return 1


@rfm.simple_test
class FftBenchmarkCPU(FfftBenmchmarkBase):
    valid_systems = ['*']
    spack_spec = 'fft-bench@0.3+fftw~cuda~rocm'
    spack_logfile = 'spack-build-log-fftw.txt'

    # Arguments to pass to the program above to run the benchmarks.
    # -o str = Path to outputfile
    # -f Run with FFTW3 Library
    # -n Run with NVIDIA cuFFT Library
    # -a Run with AMD rocFFT Library
    # -r int = Number of runs to perform (min 1, max 7)
    # -c int = Number of times to repeat the transforms, for averaging times.
    fft_output_file = './FFTW_only.txt'
    executable_opts = ["-o", fft_output_file, "-f", "-r", NUMBER_OF_TRANSFORMS, "-c", NUMBER_OF_REPEATS]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("fftw")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

@rfm.simple_test
class FftBenchmarkMKL(FfftBenmchmarkBase):
    valid_systems = ['-gpu']
    spack_spec = 'fft-bench@0.3+mkl'
    fft_output_file = "./MKL_only.txt"
    executable_opts = ["-o", fft_output_file, "-f", "-r", NUMBER_OF_TRANSFORMS, "-c", NUMBER_OF_REPEATS]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("mkl")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

@rfm.simple_test
class FftBenchmarkCUDA(FfftBenmchmarkBase):
    valid_systems = ['+gpu +cuda']
    spack_spec = 'fft-bench@0.3+cuda~rocm'
    spack_logfile = 'spack-build-log-cuda.txt'
    num_gpus_per_node = 1

    fft_output_file = 'FFTW_cuFFT.txt'
    executable_opts = ["-o", fft_output_file, "-f", "-n", "-r", NUMBER_OF_TRANSFORMS, "-c", NUMBER_OF_REPEATS]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("fftw+cuda")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'
        self.extra_resources['gpu'] = {'num_gpus_per_node': self.num_gpus_per_node}

@rfm.simple_test
class FftBenchmarkROCM(FfftBenmchmarkBase):
    valid_systems = ['+gpu +rocm']
    spack_spec = 'fft-bench@0.3+rocm~cuda'
    spack_logfile = 'spack-build-log-rocm.txt'
    num_gpus_per_node = 1

    fft_output_file = 'FFTW_rocFFT.txt'
    executable_opts = ["-o", fft_output_file, "-f", "-a", "-r", NUMBER_OF_TRANSFORMS, "-c", NUMBER_OF_REPEATS]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("fftw+rocm")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'
        self.extra_resources['gpu'] = {'num_gpus_per_node': self.num_gpus_per_node}
