import pathlib, os

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function, variable

from benchmarks.modules.utils import SpackTest

NUMBER_OF_TRANSFORMS = '7'
NUMBER_OF_REPEATS = '10'

class FftBenmchmarkBase(SpackTest):
    # Systems and programming environments where to run this benchmark.
    # Systems/partitions can be identified by their features, `+feature` is a
    # partition which has the named feature, `-feature` is a partition which
    # does not have the named feature.  This is a CPU-only benchmark, so we use
    # `-gpu` to exclude GPU partitions.
    bench_name = "FFT_Bench"
    output_dict_list = []
    valid_systems = ['*']
    valid_prog_environs = ['default']
    tasks = parameter([1])
    num_tasks_per_node = 1
    cpus_per_task = parameter([16])
    time_limit = '2h'
    container_path = variable(str, value="/opt/uksrc-excalibur-tests")
    transform_count = variable(str, value=NUMBER_OF_TRANSFORMS)
    repeat_count = variable(str, value=NUMBER_OF_REPEATS)

    executable = 'FFT_Bench'

    reference = {
        'myriad': {
            'Libarary': ("FFTW", None, None, None),
            'Size': (1., None, None, 'MB'),
            'Time': (1., None, None, 'miliseconds'),
        }
    }

    output_file = "default.txt"

    @run_before('setup')
    def set_container_cmd(self):
        import inspect
        path = inspect.getfile(type(self))
        self.container_cmd = f'reframe --system=default -c {self.container_path}/{path[path.find("benchmarks/apps"):]} -n {type(self).__name__} -S {type(self).__name__}.transform_count={self.transform_count} -S {type(self).__name__}.repeat_count={self.repeat_count} -r'

    @run_before('setup')
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
        return sn.assert_true(os.path.isfile(self.outputdir + '/' + self.output_file))

    @run_before("performance")
    def output_list_dict(self):
        """
        In order to use the database handler perflog 'swiftdb', self.output_dict_list must be defined.
        This dictionary should include at least:
        - TimeOfTest [str]
        - SystemPartition [str]
        - <Desired Output variables> [Format Determinable]
        """
        pattern = r'(?P<Library>\S+), (?P<Mem_Size>\S+), (?P<ExecutionTime>\S+),'
        output_list = sn.extractall(pattern,
                                    pathlib.Path(self.outputdir) / self.output_file,
                                    ['Library', 'Mem_Size', 'ExecutionTime'],
                                    [str, float, float])
        time_of_test = str(dt.now().strftime("%Y-%m-%d-%H:%M"))

        for output in output_list:
            self.output_dict_list += [
                {
                    "TimeOfTest": time_of_test,
                    "SystemPartition": f"{os.environ.get('GH_RUNNER')} - {self.current_system.name} - {self.current_partition.name}",
                    "Library": output[0],
                    "ArraySizeMB": output[1],
                    "ExecutionTime":output[2]
                }
            ]
        return

    @performance_function('notAmetric')
    def dummy_perf(self):
        return 1


@rfm.simple_test
class FftBenchmarkCPU(FftBenmchmarkBase):
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
    output_file = 'FFTW_only.txt'

    @run_before('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("+fftw")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'

    @run_after('setup')
    def setting_call(self):
        self.executable_opts = ["-o", f"{self.outputdir}/{self.output_file}", "-f", "-r", self.transform_count, "-c", self.repeat_count]


@rfm.simple_test
class FftBenchmarkCUDA(FftBenmchmarkBase):
    valid_systems = ['+gpu +cuda']
    spack_spec = 'fft-bench@0.3+fftw+cuda~rocm'
    spack_logfile = 'spack-build-log-cuda.txt'
    num_gpus_per_node = 1
    output_file = 'FFTW_cuFFT.txt'

    @run_before('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("+fftw+cuda")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'
        self.extra_resources['gpu'] = {'num_gpus_per_node': self.num_gpus_per_node}

    @run_after('setup')
    def setting_call(self):
        self.executable_opts = ["-o", f"{self.outputdir}/{self.output_file}", "-f", "-n", "-r", self.transform_count, "-c", self.repeat_count]

@rfm.simple_test
class FftBenchmarkROCM(FftBenmchmarkBase):
    valid_systems = ['+gpu +rocm']
    spack_spec = 'fft-bench@0.3+fftw+rocm~cuda'
    spack_logfile = 'spack-build-log-rocm.txt'
    num_gpus_per_node = 1
    output_file = 'FFTW_rocFFT.txt'

    @run_before('setup')
    def setup_variables(self):
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task
        self.tags.add("+fftw+rocm")
        self.env_vars['OMP_NUM_THREADS'] = f'{self.num_cpus_per_task}'
        self.extra_resources['gpu'] = {'num_gpus_per_node': self.num_gpus_per_node}

    @run_after('setup')
    def setting_call(self):
        self.executable_opts = ["-o", f"{self.outputdir}/{self.output_file}", "-f", "-a", "-r", self.transform_count, "-c", self.repeat_count]
