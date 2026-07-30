import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest

# THE SOURCE TEST DOES NOT FUNCTION AT THIS TIME.
@rfm.simple_test
class STARSimagecutoutsastropy(STARSTest):
    stars_name="imagecutoutsastropy"
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/image-cutouts-astropy"
    container_url = container_image

    container_precmd += "cd /scripts\nln -s /astro-cutouts/examples /examples\n"
    container_cmd = "python3 /scripts/cutouts.py --format png --geometry 3x3 /examples/Sources.lis"
    execute_script = container_cmd

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        return sn.all([
            super().validate(),
        ])