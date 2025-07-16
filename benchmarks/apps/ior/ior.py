# Import modules from reframe and excalibur-tests
import reframe as rfm
import reframe.utility.sanity as sn
from reframe.core.backends import getlauncher
from benchmarks.modules.utils import SpackTest

import string
import secrets

@rfm.simple_test
class IORBenchmark(SpackTest):

    # Run configuration
    block_size = variable(str, value="1m")
    transfer_size = variable(str, value="1m")
    directory = variable(str, value=".")
    filename = ''.join(secrets.choice(string.ascii_letters) for _ in range(16))

    patterns = {
        "read":r'read\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)',
        "write":r'write\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)'
    }

    ## Mandatory ReFrame setup
    valid_systems = ['-gpu']
    valid_prog_environs = ['default']

    spack_spec = 'ior openmpi'

    ## Executable
    executable = 'ior'
    ##executable_opts = [f"-b={self.block_size}", f"-t={self.transfer_size}"]

    ## Scheduler options
    tasks = variable(int, value=2)  # Used to set `num_tasks` in `__init__`.
    cpus_per_task = 1

    time_limit = '5m'
    use_multithreading = False

    ## Reference performance values
    reference = {

    }

    def __init__(self):
        # The number of tasks and CPUs per task need to be set here because
        # accessing a test parameter from the class body is not allowed.
        self.num_tasks = self.tasks
        self.num_cpus_per_task = self.cpus_per_task

    @run_before("run")
    def set_options(self):
        self.executable_opts = [f"-b={self.block_size}", f"-t={self.transfer_size}", f"-o {self.directory}/ior_test_{self.filename}"]


    @run_before('sanity')
    def set_sanity_patterns(self):
        # Check that the string `[RESULT][0]` appears in the standard output of
        # the program.
        self.sanity_patterns = sn.assert_found(r'Finished.*', self.stdout)

    @performance_function('MiB/s')
    def read_bw(self):
        return sn.extractsingle(self.patterns["read"], self.stdout,1, float)

    @performance_function('MiB/s')
    def write_bw(self):
        return sn.extractsingle(self.patterns["write"], self.stdout,1, float)

    @performance_function('IOPS')
    def read_iops(self):
        return sn.extractsingle(self.patterns["read"], self.stdout,2, float)

    @performance_function('IOPS')
    def write_iops(self):
        return sn.extractsingle(self.patterns["write"], self.stdout,2, float)

    @performance_function('seconds')
    def read_latency(self):
        return sn.extractsingle(self.patterns["read"], self.stdout,3, float)

    @performance_function('seconds')
    def write_latency(self):
        return sn.extractsingle(self.patterns["write"], self.stdout,3, float)

    @performance_function('KiB')
    def test_xfersize(self):
        return sn.extractsingle(self.patterns["read"], self.stdout,4, float)

    @performance_function('KiB')
    def test_blocksize(self):
        return sn.extractsingle(self.patterns["read"], self.stdout,5, float)