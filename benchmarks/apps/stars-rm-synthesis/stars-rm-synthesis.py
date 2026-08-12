import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest

# THE TEST DOES NOT FUNCTION ON LOCAL LAPTOP, NEEDS TESTING ON HPC
@rfm.simple_test
class STARSrmsynthesis(STARSTest):
    stars_name="rm-synthesis"
    valid_systems = ["-low_memory"]
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/rm-synthesis"

    container_precmd += "cd ..\n/scripts/get-data.sh\ncd /data\n"

    container_cmd = "/scripts/run-rmsynth3d.sh"

    reference_time = 915.0

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        return sn.all([
            super().validate(),
        ])