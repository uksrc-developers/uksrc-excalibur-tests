import os
import sys
import reframe as rfm
import reframe.utility.sanity as sn
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after
from benchmarks.modules.utils import SpackTest

NUMBER_OF_TRANSFORMS = '1'
NUMBER_OF_REPEATS = '1'

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

    output_file = "./default.txt"

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
        return sn.assert_found(r'Run_Finished', self.output_file)

    # A performance benchmark.
    #@run_before('performance')
    #def set_perf_patterns(self):
    #    output_list = sn.extractall( r'<Library>,\t\t<Size>,\t\t<Time>,',
    #                                 self.stdout,
    #                                 ['Library', 'Size', 'Time'],
    #                                 [str, float, float])
    #    self.perf_patterns = {
    #        'Libarary': output_list[0],
    #        'Size': output_list[1],
    #        'Time': output_list[2]
    #    }

@rfm.simple_test
class FftBenchmarkCPU(FfftBenmchmarkBase):
    valid_systems = ['-gpu']
    spack_spec = 'fft-bench@0.3+fftw~cuda~rocm'
    spack_logfile = 'spack-build-log-fftw.txt'

    # Arguments to pass to the program above to run the benchmarks.
    # -o str = Path to outputfile
    # -f Run with FFTW3 Library
    # -n Run with NVIDIA cuFFT Library
    # -a Run with AMD rocFFT Library
    # -r int = Number of runs to perform (min 1, max 7)
    # -c int = Number of times to repeat the transforms, for averaging times.
    output_file = '"./FFTW_only.txt"'
    executable_opts = ["-o", output_file, "-f", "-r", NUMBER_OF_TRANSFORMS, "-c", NUMBER_OF_REPEATS]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("fftw")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

#@rfm.simple_test
#class FftBenchmarkMKL(FfftBenmchmarkBase):
#    valid_systems = ['-gpu']
#    spack_spec = 'fft-bench@0.3+mkl'
#    output_file = "./MKL_only.txt"
#    executable_opts = ["-o", output_file, "-f", "-r", number_of_memory_points, "-c", number_of_runs]
#
#    @run_after('setup')
#    def setup_variables(self):
#        self.num_tasks = self.tasks
#        self.num_cpus_per_task = self.cpus_per_task
#        self.tags.add("mkl")
#        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

@rfm.simple_test
class FftBenchmarkCUDA(FfftBenmchmarkBase):
    valid_systems = ['+gpu +cuda']
    spack_spec = 'fft-bench@0.3+cuda~rocm'
    spack_logfile = 'spack-build-log-cuda.txt'
    num_gpus_per_node = 1

    output_file = '"FFTW_cuFFT.txt"'
    executable_opts = ["-o", output_file, "-f", "-n", "-r", NUMBER_OF_TRANSFORMS, "-c", NUMBER_OF_REPEATS]

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

    output_file = '"FFTW_rocFFT.txt"'
    executable_opts = ["-o", output_file, "-f", "-a", "-r", NUMBER_OF_TRANSFORMS, "-c", NUMBER_OF_REPEATS]

    @run_after('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("fftw+rocm")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'
        self.extra_resources['gpu'] = {'num_gpus_per_node': self.num_gpus_per_node}