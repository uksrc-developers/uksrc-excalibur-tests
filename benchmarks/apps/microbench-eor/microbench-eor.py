import pathlib, os, subprocess, json

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function

from astropy.io import fits

@rfm.simple_test
class MicrobenchEOR(rfm.RunOnlyRegressionTest):
    bench_name="MicrobenchEOR"
    valid_systems = ['*']
    valid_prog_environs = ['default']

    eor_code_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "EOR_Code")
    eor_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "EOR_Data")
    os.makedirs(eor_data_dir, exist_ok=True)

    hera_pspec_dir = os.path.join(eor_code_dir, 'hera_pspec')

    tasks = parameter([1])
    num_tasks_per_node = 1
    cpus_per_task = parameter([16])

    executable = "apptainer"

    output_dict_list = []

    @run_before('setup')
    def build_singularity(self):
        if not os.path.isfile(os.path.join(self.eor_code_dir, "singularity_images/hera-pspec-mambaorg.sif")):
            og_dir = os.getcwd()
            os.chdir(os.path.join(self.eor_code_dir, "singularity_images"))
            subprocess.run(f"singularity build hera-pspec-mambaorg.sif hera-pspec-mambaorg.def", shell=True)
            os.chdir(og_dir)

    @run_before('setup')
    def download_data(self):
        data_set = os.path.join(self.eor_data_dir, "NF_HERA_Dipole_power_beam_healpix.fits")
        if not os.path.isfile(data_set):
            file = f"https://object.arcus.openstack.hpc.cam.ac.uk/swift/v1/AUTH_7ac3c0a502cd46c783b2128116165566/microbench_data/EoR/NF_HERA_Dipole_power_beam_healpix.fits"
            file_name = data_set
            subprocess.run(f"wget -O {file_name} {file}", shell=True)

    @run_before('run')
    def add_prerun_cmds(self):
        self.prerun_cmds = [
            f"echo \"Workflow start: $(date '+%Y-%m-%d %H:%M:%S')\" > {self.outputdir}/output.log"
        ]

    @run_before('run')
    def set_executable_opts(self):
        os.mkdir(os.path.join(self.outputdir, "outputs"))
        self.executable_opts = [
            "run",
            "--bind", f"{self.eor_data_dir}:/data",
            "--bind", f"{self.outputdir}:/project",
            os.path.join(self.eor_code_dir, 'singularity_images/hera-pspec-mambaorg.sif'),
            os.path.join(self.eor_code_dir, "scripts/pspec_params_micro.yaml")
        ]

    @run_after('run')
    def post_run_cmd(self):
        subprocess.run(f"echo \"Workflow end: $(date '+%Y-%m-%d %H:%M:%S')\" >> {self.outputdir}/output.log", shell=True)

    @sanity_function
    def validate(self):
        with open(os.path.join(self.stagedir, "rfm_job.out")) as myfile:
            if "All PSPEC MERGE jobs ran through" in myfile.read():
                return True
            else:
                return False

    @run_before("performance")
    def output_list_dict(self):
        """
        In order to use the database handler perflog 'swiftdb', self.output_dict_list must be defined.
        This dictionary should include at least:
        - TimeOfTest [str]
        - SystemPartition [str]
        - <Desired Output variables> [Format Determinable]
        """
        start_str = sn.evaluate(sn.extractsingle(
            r'Workflow start: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
            pathlib.Path(self.outputdir) / pathlib.Path("output.log"),
            tag=1
        ))
        finish_str = sn.evaluate(sn.extractsingle(
            r'Workflow end: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
            pathlib.Path(self.outputdir) / pathlib.Path("output.log"),
            tag=1
        ))
        start = dt.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        finish = dt.strptime(finish_str, "%Y-%m-%d %H:%M:%S")

        elapsed_seconds = (finish - start).total_seconds()

        time_of_test = str(dt.now().strftime("%Y-%m-%d %H:%M:%S"))

        self.output_dict_list += [
            {
                "TimeOfTest": time_of_test,
                "SystemPartition": f"{os.environ.get('GH_RUNNER')} - {self.current_system.name} - {self.current_partition.name}",
                "ExecutionTime": elapsed_seconds
            }
        ]
        print(self.output_dict_list)

    @performance_function('notAmetric')
    def dont_send_confluence(self):
        return 1

    @run_after('performance')
    def free_space(self):
        og_dir = os.getcwd()
        os.chdir(os.path.join(self.eor_code_dir, "singularity_images"))
        subprocess.run(f"rm -f hera-pspec-mambaorg.sif", shell=True)
        subprocess.run(f"rm -f {os.path.join(self.eor_data_dir, 'NF_HERA_Dipole_power_beam_healpix.fits')}", shell=True)
        os.chdir(og_dir)