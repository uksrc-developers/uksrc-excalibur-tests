import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest

# THE SOURCE TEST DOES NOT FUNCTION AT THIS TIME.
@rfm.simple_test
class STARSimagecutoutssoda(STARSTest):
    stars_name="image-cutouts-soda"
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/image-cutouts-soda"
    container_url = container_image

    dataset = [{"filename": "M51_field_10_brightest.lis",
                "url": "https://gitlab.com/ska-telescope/src/src-workloads/-/raw/main/tasks/image-cutouts-soda/examples/M51_field_10_brightest.lis"}]
    container_datadir = "/examples"
    container_precmd += "cd /scripts\nmkdir /examples\n"
    container_cmd = "./pipeline.sh"
    execute_script = container_cmd

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        return sn.all([
            super().validate(),
        ])