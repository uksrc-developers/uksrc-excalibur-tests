import pathlib, os, subprocess, json

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function

from benchmarks.modules.utils import ContainerTest

from astropy.io import fits

@rfm.simple_test
class STARSpulsarsearchpresto(ContainerTest):
    bench_name="STARSpulsarsearchpresto"
    valid_systems = ['*']
    valid_prog_environs = ['default']
    run_only_test = True

    code_dir = ""
    data_dir = ""

    tasks = parameter([1])
    num_tasks_per_node = 1
    cpus_per_task = parameter([4])

    executable = "singularity"

    output_dict_list = []

    @run_after('setup')
    def copy_dirs_stage(self):
        self.code_dir = os.path.join(self.stagedir, "STARS_psp_Code")
        os.makedirs(self.code_dir, exist_ok=True)
        self.data_dir = os.path.join(self.stagedir, "STARS_psp_Data")
        os.makedirs(self.data_dir, exist_ok=True)

    @run_after('setup')
    def download_code(self):
        if not os.path.isfile(os.path.join(self.code_dir, "singularity_images/pulsar-search-presto.sif")):
            subprocess.run(
                f"mkdir {os.path.join(self.code_dir, 'singularity_images')}",
                shell=True
            )
            subprocess.run(
                f"singularity pull docker://registry.gitlab.com/ska-telescope/src/src-workloads/pulsar-search-presto",
                shell=True)
            subprocess.run(f"mv pulsar-search-presto_latest.sif {os.path.join(self.code_dir, 'singularity_images/pulsar-search-presto.sif')}", shell=True)
        if not os.path.isfile(os.path.join(self.data_dir, "splice_0001.fits")):
            subprocess.run(f"wget -nc https://zenodo.org/records/10989783/files/splice_0001.fits?download=1 -O {os.path.join(self.data_dir, 'splice_0001.fits')}", shell=True)


    @run_before('run')
    def add_prerun_cmds(self):
        self.prerun_cmds = [
            f"touch {self.stagedir}/rfm_build.out",
            f"touch {self.stagedir}/rfm_build.err",
            f"touch {self.stagedir}/rfm_build.sh",
            f"echo '#!/bin/bash' >> {self.outputdir}/ssh_job.sh",
            f"echo '/scripts/run-task.sh' >> {self.outputdir}/ssh_job.sh",
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
            "--no-home",
            "--bind",
            f"{self.outputdir}:/output",
            "--bind",
            f"{self.data_dir}:/data",
            os.path.join(self.code_dir, "singularity_images/pulsar-search-presto.sif"),
            f"bash",
            os.path.join("/output/ssh_job.sh")
        ]

    @sanity_function
    def validate(self):
        #test_fits = fits.open(os.path.join(self.outputdir, "crossmatch_cat.fits"))
        #return test_fits[1].data.shape[0] > 0
        return True

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
