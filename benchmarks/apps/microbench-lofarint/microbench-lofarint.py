import pathlib, os, subprocess, json

from datetime import datetime as dt
import reframe.utility.sanity as sn

import reframe as rfm
from reframe.core.backends import getlauncher
from reframe.core.builtins import sanity_function, parameter, run_before, run_after, performance_function

from benchmarks.modules.utils import ContainerTest

@rfm.simple_test
class MicrobenchLOFARINT(ContainerTest):
    bench_name="MicrobenchLOFARINT"
    valid_systems = ['*']
    valid_prog_environs = ['default']
    output_file = "Default.txt"
    run_only_test = True

    code_dir = ""
    LINC_dir = ""
    VLBI_dir = ""
    vlbi_singularity_dir = ""
    data_dir = ""

    tasks = parameter([1])
    num_tasks_per_node = 1
    cpus_per_task = parameter([16])

    executable = "toil-cwl-runner"

    log_dir = ""
    work_dir = ""
    job_dir = ""
    output_dir = ""
    tmpout_dir = ""

    output_dict_list = []

    @run_after('setup')
    def copy_dirs_stage(self):
        self.code_dir = os.path.join(self.stagedir, "LOFARINT_Code")
        os.makedirs(self.code_dir, exist_ok=True)
        self.LINC_dir = os.path.join(self.code_dir, "LINC")
        self.VLBI_dir = os.path.join(self.code_dir, "VLBI-cwl")
        self.vlbi_singularity_dir = os.path.join(self.code_dir, "singularity_images")
        os.makedirs(self.vlbi_singularity_dir, exist_ok=True)

        self.data_dir = os.path.join(self.stagedir, "LOFARINT_Data")
        os.makedirs(self.data_dir, exist_ok=True)

    @run_after('setup')
    def download_linc(self):
        if not os.path.exists(self.LINC_dir):
            subprocess.run(f"git clone https://git.astron.nl/RD/LINC.git --branch releases/v5.1 {self.LINC_dir}", shell=True)

    @run_after('setup')
    def download_vlbi(self):
        if not os.path.exists(self.VLBI_dir):
            subprocess.run(f"git clone https://git.astron.nl/RD/VLBI-cwl.git {self.VLBI_dir}", shell=True) #, "--branch", "0.8.0", self.VLBI_dir])

    @run_after('setup')
    def download_singularity_image(self):
        vlbi_singularity_sif = os.path.join(self.vlbi_singularity_dir, "flocs_v6.0.0_sandybridge_sandybridge.sif")
        if not os.path.isfile(vlbi_singularity_sif):
            subprocess.run(f"wget -q -O {vlbi_singularity_sif} https://public.spider.surfsara.nl/project/lofarvwf/fsweijen/containers/flocs_v6.0.0_sandybridge_sandybridge.sif", shell=True)

        vlbi_singularity_link = os.path.join(self.vlbi_singularity_dir, "vlbi-cwl.sif")
        if not os.path.isfile(vlbi_singularity_link):
            subprocess.run(f"ln -s {vlbi_singularity_sif} {vlbi_singularity_link}", shell=True)

        vlbi_singularity_latest_link = os.path.join(self.vlbi_singularity_dir, "vlbi-cwl_latest.sif")
        if not os.path.isfile(vlbi_singularity_latest_link):
            subprocess.run(f"ln -s {vlbi_singularity_sif} {vlbi_singularity_latest_link}", shell=True)

        vlbi_singularity_latest_link_colon = os.path.join(self.vlbi_singularity_dir, "vlbi-cwl:latest.sif")
        if not os.path.isfile(vlbi_singularity_latest_link_colon):
            subprocess.run(f"ln -s {vlbi_singularity_sif} {vlbi_singularity_latest_link_colon}", shell=True)

    @run_after('setup')
    def download_data(self):
        if not os.path.isdir(os.path.join(self.data_dir, "L693725_SB282_uv.MS")):
            address = "https://object.arcus.openstack.hpc.cam.ac.uk/swift/v1/AUTH_7ac3c0a502cd46c783b2128116165566/microbench_data/"
            subprocess.run("wget -qO- {Address} | grep '^LOFARINT/' | xargs -n1 -I".format(Address=address)+"{} wget -nH --cut-dirs=5 -R 'index.html' -x -P "+"{DataDir} {Address}".format(Address=address, DataDir=self.data_dir)+"{}", shell=True)
            og_dir = os.getcwd()
            os.chdir(os.path.join(self.data_dir, "L693725_SB282_uv.MS"))
            subprocess.run("cat table.f3.tar.gz.* | tar xzvf -", shell=True)
            os.chdir(og_dir)

    @run_before('run')
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
            f"touch {self.stagedir}/rfm_build.out",
            f"touch {self.stagedir}/rfm_build.err",
            f"touch {self.stagedir}/rfm_build.sh",
            f'export CWL_SINGULARITY_CACHE={self.vlbi_singularity_dir}',
            "export SINGULARITY_CACHEDIR=${CWL_SINGULARITY_CACHE}",
            "export APPTAINER_CACHEDIR=${CWL_SINGULARITY_CACHE}",
            'export APPTAINERENV_PREPEND_PATH=${APPTAINERENV_PREPEND_PATH:-"' + self.VLBI_dir + '/scripts"}',
            'export APPTAINERENV_PYTHONPATH=${APPTAINERENV_PYTHONPATH:-"' + self.VLBI_dir + '/scripts:${PYTHONPATH}"}',
            f"export APPTAINER_BIND={os.path.join(self.outputdir, 'toil')},{self.code_dir}/VLBI-cwl,{self.data_dir}",
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
            f'{self.data_dir}/parameters.json"',
            '',
            'env APPTAINERENV_PREPEND_PATH="$APPTAINERENV_PREPEND_PATH" '
            'APPTAINERENV_PYTHONPATH="$APPTAINERENV_PYTHONPATH" '
            'APPTAINER_BIND="$APPTAINER_BIND" '
            '"${TOIL_COMMAND}" > '+self.output_dir+'setup.out && STATUS=${?} || STATUS=${?}',
            f"echo \"Workflow start: $(date '+%Y-%m-%d %H:%M:%S')\" > {self.outputdir}/output.log"
        ]
        self.postrun_cmds = [
            f"echo \"Workflow end: $(date '+%Y-%m-%d %H:%M:%S')\" >> {self.outputdir}/output.log"
        ]

    @run_after('setup')
    def creat_json(self):
        json_for_test = {
            "msin": [
                {
                    "class": "Directory",
                    "path": os.path.join(self.data_dir, "L693725_SB282_uv.MS")
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
                "path": os.path.join(self.data_dir, "models/delay_calibrators.csv")
            },
            "configfile": {
                "class": "File",
                "path": os.path.join(self.data_dir, "models/facetselfcal_config.txt")
            },
            "selfcal": {
                "class": "Directory",
                "path": os.path.join(self.data_dir, "models/lofar_facet_selfcal/")
            },
            "h5merger": {
                "class": "Directory",
                "path": os.path.join(self.data_dir, "models/lofar_helpers/")
            },
            "solset": {
                "class": "File",
                "path": os.path.join(self.data_dir, "models/cal_solutions.h5")
            }
        }
        # Serializing json
        json_object = json.dumps(json_for_test, indent=4)
        # Writing to sample.json
        with open(os.path.join(self.data_dir, "parameters.json"), "w") as outfile:
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
            f"{self.data_dir}/parameters.json"
        ]

    @sanity_function
    def validate(self):
        with open(os.path.join(self.stagedir, "rfm_job.err")) as myfile:
            if "Success: True" in myfile.read():
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

#    @performance_function('notAmetric')
#    def dont_send_confluence(self):
#        return 1
