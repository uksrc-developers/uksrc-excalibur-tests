import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest

@rfm.simple_test
class STARSsourcefindingpybdsf(STARSTest):
    stars_name="source-finding-pybdsf"
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/source-finding-pybdsf"
    container_url = container_image

    container_precmd += "cd ..\n/scripts/get-data.sh\ncd /data\n"

    container_cmd = "/scripts/LOTSS-P21-1image/LOTSS-P21-sourcefinding.sh"
    execute_script = container_cmd

    reference_time = 46.67

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        return sn.all([
            super().validate(),
        ])