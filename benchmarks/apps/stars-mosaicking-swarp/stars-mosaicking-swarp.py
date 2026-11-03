import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest

@rfm.simple_test
class STARSmosaickingswarp(STARSTest):
    stars_name="mosaicking-swarp"
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/mosaicking-swarp"
    container_url = container_image

    container_precmd += "cd ..\n/scripts/get-data.sh\ncd /data\n"

    container_cmd = "/scripts/run-task.sh"
    execute_script = container_cmd

    reference_time = 34.33

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        return sn.all([
            super().validate(),
        ])