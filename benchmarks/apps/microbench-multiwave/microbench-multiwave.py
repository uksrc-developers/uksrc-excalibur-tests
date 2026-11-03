import pathlib, os, subprocess, json

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function

from astropy.io import fits

from benchmarks.modules.utils import ContainerTest


@rfm.simple_test
class MicrobenchMULTIWAVE(ContainerTest):
    bench_name="MicrobenchMULTIWAVE"
    valid_systems = ['*']
    valid_prog_environs = ['default']
    run_only_test = True

    code_dir = ""
    data_dir = ""

    tasks = parameter([1])
    num_tasks_per_node = 1
    cpus_per_task = parameter([16])

    executable = "singularity"

    output_dict_list = []

    @run_after('setup')
    def copy_dirs_stage(self):
        self.code_dir = os.path.join(self.stagedir, "MULTIWAVE_Code")
        os.makedirs(self.code_dir, exist_ok=True)
        self.data_dir = os.path.join(self.stagedir, "MULTIWAVE_Data")
        os.makedirs(self.data_dir, exist_ok=True)

    @run_after('setup')
    def download_code(self):
        if not os.path.isfile(os.path.join(self.code_dir, "singularity_images/pybdsf.sif")):
            subprocess.run(
                f"git clone https://github.com/uksrc-developers/MW-sourcefind.git {self.code_dir}",
                shell=True)
            subprocess.run(
                f"mkdir {os.path.join(self.code_dir, 'singularity_images')}",
                shell=True
            )
            subprocess.run(
                    f"mv {os.path.join(self.code_dir, 'pybdsf.singularity')} {os.path.join(self.code_dir, 'singularity_images/pybdsf.singularity')}",
                shell=True
            )
            subprocess.run(
                f"singularity build {os.path.join(self.code_dir, 'singularity_images/pybdsf.sif')} {os.path.join(self.code_dir, 'singularity_images/pybdsf.singularity')}",
                shell=True
            )

    @run_after('setup')
    def download_data(self):
        data_set = os.path.join(self.data_dir, "low-mosaic-blanked.fits")
        if not os.path.isfile(data_set):
            file = f"https://lofar-surveys.org/public/DR2/mosaics/P000+23/low-mosaic-blanked.fits"
            file_name = data_set
            subprocess.run(f"wget -O {file_name} {file}", shell=True)

    @run_before('run')
    def add_prerun_cmds(self):
        self.prerun_cmds = [
            f"echo '#!/bin/bash' >> {self.outputdir}/ssh_job.sh",
            f"echo 'sourcefind.py --intfile low-mosaic-blanked.fits' >> {self.outputdir}/ssh_job.sh",
            f"cp {self.data_dir}/low-mosaic-blanked.fits {self.outputdir}/low-mosaic-blanked.fits",
            f"cd {self.outputdir}",
            f"echo \"Workflow start: $(date '+%Y-%m-%d %H:%M:%S')\" > {self.outputdir}/output.log"
        ]
        self.postrun_cmds = [
            f"echo \"Workflow end: $(date '+%Y-%m-%d %H:%M:%S')\" >> {self.outputdir}/output.log"
        ]

    @run_before('run')
    def set_executable_opts(self):
        os.mkdir(os.path.join(self.outputdir, "logs"))
        self.executable_opts = [
            "exec",
            os.path.join(self.code_dir, "singularity_images/pybdsf.sif"),
            f"bash",
            os.path.join(self.outputdir, "ssh_job.sh")
        ]

    @run_after('run')
    def post_run_cmd(self):
        subprocess.run(f"echo \"Workflow end: $(date '+%Y-%m-%d %H:%M:%S')\" >> {self.outputdir}/output.log", shell=True)

    @sanity_function
    def validate(self):
        test_fits = fits.open(os.path.join(self.outputdir, "low-mosaic-blanked--final.srl.fits"))
        return test_fits[1].data.shape[0] > 0

    @run_before("performance")
    def output_list_dict(self):
        """
        In order to use the database handler perflog 'swiftdb', self.output_dict_list must be defined.
        This dictionary should include at least:
        - TimeOfTest [str]
        - SystemPartition [str]
        - <Desired Output variables> [Format Determined by entry]
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

#    @performance_function('notAmetric')
#    def dont_send_confluence(self):
#        return 1
