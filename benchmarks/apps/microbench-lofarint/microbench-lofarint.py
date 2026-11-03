import pathlib, os, subprocess, json

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function


@rfm.simple_test
class MicrobenchLOFARINT(rfm.RunOnlyRegressionTest):
    valid_systems = ['*']
    valid_prog_environs = ['default']

    lofarint_code_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LOFARINT_Code")
    os.makedirs(lofarint_code_dir, exist_ok=True)
    LINC_dir = os.path.join(lofarint_code_dir, "LINC")
    VLBI_dir = os.path.join(lofarint_code_dir, "VLBI-cwl")
    lofarint_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LOFARINT_Data")
    os.makedirs(lofarint_data_dir, exist_ok=True)
    vlbi_singularity_dir = os.path.join(lofarint_code_dir, "singularity_images")

    tasks = parameter([1])
    num_tasks_per_node = 1
    cpus_per_task = parameter([16])

    executable = "toil-cwl-runner"

    log_dir = ""
    work_dir = ""
    job_dir = ""
    output_dir = ""
    tmpout_dir = ""

    @run_before('setup')
    def download_linc(self):
        if not os.path.exists(self.LINC_dir):
            subprocess.call(["git", "clone", "https://git.astron.nl/RD/LINC.git", "--branch", "v5.1", self.LINC_dir])

    @run_before('setup')
    def download_vlbi(self):
        if not os.path.exists(self.VLBI_dir):
            subprocess.call(["git", "clone", "https://git.astron.nl/RD/VLBI-cwl.git", self.VLBI_dir]) #, "--branch", "0.8.0", self.VLBI_dir])

    @run_before('setup')
    def download_singularity_image(self):
        vlbi_singularity_sif = os.path.join(self.vlbi_singularity_dir, "flocs_v6.0.0_sandybridge_sandybridge.sif")
        if not os.path.isfile(vlbi_singularity_sif):
            subprocess.call(["wget", "-O", vlbi_singularity_sif, "https://lofar-webdav.grid.sara.nl/software/shub_mirror/tikk3r/lofar-grid-hpccloud/intel/flocs_v6.0.0_sandybridge_sandybridge.sif?action=show"])

        vlbi_singularity_link = os.path.join(self.vlbi_singularity_dir, "vlbi-cwl.sif")
        if not os.path.isfile(vlbi_singularity_link):
            subprocess.call(["ln", "-s", vlbi_singularity_sif, vlbi_singularity_link])

        vlbi_singularity_latest_link = os.path.join(self.vlbi_singularity_dir, "vlbi-cwl_latest.sif")
        if not os.path.isfile(vlbi_singularity_latest_link):
            subprocess.call(["ln", "-s", vlbi_singularity_sif, vlbi_singularity_latest_link])

        vlbi_singularity_latest_link_colon = os.path.join(self.vlbi_singularity_dir, "vlbi-cwl:latest.sif")
        if not os.path.isfile(vlbi_singularity_latest_link_colon):
            subprocess.call(["ln", "-s", vlbi_singularity_sif, vlbi_singularity_latest_link_colon])

    @run_before('setup')
    def download_data(self):
        if not os.path.isdir(os.path.join(self.lofarint_data_dir, "L693725_SB282_uv.MS")):
            file = f"https://object.arcus.openstack.hpc.cam.ac.uk/swift/v1/AUTH_7ac3c0a502cd46c783b2128116165566/microbench_data/LOFARINT"
            subprocess.call(["wget", "-O", self.lofarint_data_dir, file])
            og_dir = os.getcwd()
            os.chdir(os.path.join(self.lofarint_data_dir, "L693725_SB282_uv.MS"))
            subprocess.run(
                ["cat",
                 "table.f3.tar.gz.*",
                 "|",
                 "tar",
                 "xzvf",
                 "-",
                 ]
            )
            os.chdir(og_dir)

    @run_after('setup')
    def add_prerun_cmds(self):
        self.log_dir = os.path.join(self.outputdir, 'toil/logs/')
        self.work_dir = os.path.join(self.outputdir, 'toil/work/')
        self.job_dir = os.path.join(self.outputdir, 'toil/setup_job/')
        self.output_dir = os.path.join(self.outputdir, 'setup_results/')
        self.tmpout_dir = os.path.join(self.outputdir, 'toil/tmp/tmp')
        self.prerun_cmds = [
            f"mkdir {os.path.join(self.outputdir, 'toil')}",
            f"mkdir {os.path.join(self.outputdir, 'toil/tmp')}",
            f"mkdir {self.log_dir}",
            f"mkdir {self.work_dir}",
            f"mkdir {self.output_dir}",
            f"mkdir {self.tmpout_dir}",
            '',
            f'export CWL_SINGULARITY_CACHE={self.vlbi_singularity_dir}',
            "export SINGULARITY_CACHEDIR=${CWL_SINGULARITY_CACHE}",
            "export APPTAINER_CACHEDIR=${CWL_SINGULARITY_CACHE}",
            'export APPTAINERENV_PREPEND_PATH=${APPTAINERENV_PREPEND_PATH:-"' + self.VLBI_dir + '/scripts"}',
            'export APPTAINERENV_PYTHONPATH=${APPTAINERENV_PYTHONPATH:-"' + self.VLBI_dir + '/scripts:${PYTHONPATH}"}',
            f"export APPTAINER_BIND={os.path.join(self.outputdir, 'toil')},{self.lofarint_code_dir}/VLBI-cwl,{self.lofarint_data_dir}",
            '',
            'export TOIL_COMMAND="toil-cwl-runner '
            '--singularity '
            '--clean never ' 
            '--retryCount 0 '
            '--disableCaching '
            f'--writeLogs {self.log_dir} '
            f'--logFile {os.path.join(self.outputdir, "microbench-lofarint.log")} '
            f'--tmp-outdir-prefix {self.tmpout_dir} --workDir {self.work_dir} '
            f'--outdir {self.output_dir} --jobStore {self.job_dir} '
            '--cwl-min-ram 8589934592 '
            '--bypass-file-store '
            f'{self.VLBI_dir}/workflows/setup.cwl '
            f'{self.lofarint_data_dir}/parameters.json"',
            '',
            'env APPTAINERENV_PREPEND_PATH="$APPTAINERENV_PREPEND_PATH" '
            'APPTAINERENV_PYTHONPATH="$APPTAINERENV_PYTHONPATH" '
            'APPTAINER_BIND="$APPTAINER_BIND" '
            '"${TOIL_COMMAND}" > '+self.output_dir+'setup.out && STATUS=${?} || STATUS=${?}',
            ''
        ]

    @run_after('setup')
    def creat_json(self):
        json_for_test = {
            "msin": [
                {
                    "class": "Directory",
                    "path": os.path.join(self.lofarint_data_dir, "L693725_SB282_uv.MS")
                }
            ],
            "linc": {
                "class": "Directory",
                "path": self.LINC_dir,
            },
            "rm_correction": "RMextract",
            "Ateam_skymodel": {
                "class": "File",
                "path": os.path.join(self.LINC_dir, "skymodels/A-Team.skymodel")
            },
            "delay_calibrator": {
                "class": "File",
                "path": os.path.join(self.lofarint_data_dir, "models/delay_calibrators.csv")
            },
            "configfile": {
                "class": "File",
                "path": os.path.join(self.lofarint_data_dir, "models/facetselfcal_config.txt")
            },
            "selfcal": {
                "class": "Directory",
                "path": os.path.join(self.lofarint_data_dir, "models/lofar_facet_selfcal/")
            },
            "h5merger": {
                "class": "Directory",
                "path": os.path.join(self.lofarint_data_dir, "models/lofar_helpers/")
            },
            "solset": {
                "class": "File",
                "path": os.path.join(self.lofarint_data_dir, "models/cal_solutions.h5")
            }
        }
        # Serializing json
        json_object = json.dumps(json_for_test, indent=4)
        # Writing to sample.json
        with open(os.path.join(self.lofarint_data_dir, "parameters.json"), "w") as outfile:
            outfile.write(json_object)

    @run_before('run')
    def set_executable_opts(self):
        self.executable_opts = [
            "--singularity",
            "--clean", "never",
            "--retryCount", "0",
            "--disableCaching",
            "--writeLogs", self.log_dir,
            "--logFile", os.path.join(self.outputdir, "microbench-lofarint.log"),
            "--tmp-outdir-prefix", self.tmpout_dir,
            "--workDir", self.work_dir,
            "--outdir", self.output_dir,
            "--jobStore", self.job_dir,
            "--cwl-min-ram", "8589934592",
            "--bypass-file-store",
            f"{self.VLBI_dir}/workflows/setup.cwl",
            f"{self.lofarint_data_dir}/parameters.json"
        ]

    @sanity_function
    def validate(self):
        with open(os.path.join(self.stagedir, "rfm_job.err")) as myfile:
            if "Success: True" in myfile.read():
                return True
            else:
                return False

    @run_after('sanity')
    def free_space(self):
        subprocess.run(["rm", "-rf", os.path.join(self.outputdir, "setup_results/")])
        subprocess.run(["rm", "-rf", os.path.join(self.outputdir, "toil/")])