import pathlib, os, subprocess, json

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function

from astropy.io import fits

@rfm.simple_test
class MicrobenchMULTIWAVE(rfm.RunOnlyRegressionTest):
    valid_systems = ['*']
    valid_prog_environs = ['default']

    multiwave_code_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MULTIWAVE_Code")
    multiwave_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MULTIWAVE_Data")
    os.makedirs(multiwave_data_dir, exist_ok=True)

    tasks = parameter([1])
    num_tasks_per_node = 1
    cpus_per_task = parameter([16])

    executable = "singularity"

    @run_before('setup')
    def download_code(self):
        if not os.path.isfile(os.path.join(self.multiwave_code_dir, "singularity_images/pybdsf.sif")):
            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/uksrc-developers/MW-sourcefind.git",
                    self.multiwave_code_dir
                ]
            )
            subprocess.run(["mkdir", os.path.join(self.multiwave_code_dir, "singularity_images")])
            subprocess.run(
                [
                    "mv",
                    os.path.join(self.multiwave_code_dir, "pybdsf.singularity"),
                    os.path.join(self.multiwave_code_dir, "singularity_images/pybdsf.singularity")
                ]
            )
            subprocess.run(
                ["singularity",
                 "build",
                 os.path.join(self.multiwave_code_dir, "singularity_images/pybdsf.sif"),
                 os.path.join(self.multiwave_code_dir, "singularity_images/pybdsf.singularity")
                 ]
            )

    @run_before('setup')
    def download_data(self):
        data_set = os.path.join(self.multiwave_data_dir, "low-mosaic-blanked.fits")
        if not os.path.isfile(data_set):
            file = f"https://lofar-surveys.org/public/DR2/mosaics/P000+23/low-mosaic-blanked.fits"
            file_name = data_set
            subprocess.run(["wget", "-O", file_name, file])

    @run_before('run')
    def add_prerun_cmds(self):
        self.prerun_cmds = [
            f"echo '#!/bin/bash' >> {self.outputdir}/ssh_job.sh",
            f"echo 'sourcefind.py --intfile low-mosaic-blanked.fits' >> {self.outputdir}/ssh_job.sh",
            f"cp {self.multiwave_data_dir}/low-mosaic-blanked.fits {self.outputdir}/low-mosaic-blanked.fits",
            f"cd {self.outputdir}"
        ]

    @run_before('run')
    def set_executable_opts(self):
        os.mkdir(os.path.join(self.outputdir, "logs"))
        self.executable_opts = [
            "exec",
            os.path.join(self.multiwave_code_dir, "singularity_images/pybdsf.sif"),
            f"bash",
            os.path.join(self.outputdir, "ssh_job.sh")
        ]

    @sanity_function
    def validate(self):
        test_fits = fits.open(os.path.join(self.outputdir, "low-mosaic-blanked--final.srl.fits"))
        return test_fits[1].data.shape[0] > 0

    @run_after('sanity')
    def free_space(self):
        subprocess.run(["rm", "-rf", os.path.join(self.outputdir, "intermediate-products")])
        subprocess.run(f"rm {self.outputdir}/*.fits", shell=True, check=True)
