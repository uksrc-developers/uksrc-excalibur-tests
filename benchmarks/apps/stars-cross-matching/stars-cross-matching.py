import pathlib, os, subprocess, json

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function

from benchmarks.modules.utils import ContainerTest

from astropy.io import fits

@rfm.simple_test
class STARScrossmatch(ContainerTest):
    bench_name="STARScrossmatch"
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
        self.code_dir = os.path.join(self.stagedir, "STARS_crossmatch_Code")
        os.makedirs(self.code_dir, exist_ok=True)
        self.data_dir = os.path.join(self.stagedir, "STARS_crossmatch_Data")
        os.makedirs(self.data_dir, exist_ok=True)

    @run_after('setup')
    def download_code(self):
        if not os.path.isfile(os.path.join(self.code_dir, "singularity_images/cross-matching.sif")):
            subprocess.run(
                f"mkdir {os.path.join(self.code_dir, 'singularity_images')}",
                shell=True
            )
            subprocess.run(
                f"singularity pull docker://registry.gitlab.com/ska-telescope/src/src-workloads/cross-matching",
                shell=True)
            subprocess.run(f"mv cross-matching_latest.sif {os.path.join(self.code_dir, 'singularity_images/cross-matching.sif')}", shell=True)

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
            f"{self.data_dir}:/data",
            os.path.join(self.code_dir, "singularity_images/cross-matching.sif"),
            f"bash",
            os.path.join(self.outputdir, "ssh_job.sh")
        ]

    @sanity_function
    def validate(self):
        test_fits = fits.open(os.path.join(self.datadir, "crossmatch_cat.fits"))
        return test_fits[1].data.shape[0] > 0

