import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest

from astropy.io import fits

@rfm.simple_test
class STARScrossmatch(STARSTest):
    stars_name="crossmatching"
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/cross-matching"
    container_url = container_image

    container_cmd = "python3 /scripts/crossmatch.py"
    execute_script = container_cmd

    reference_time = 14.67

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        test_fits = fits.open(os.path.join(self.data_dir, "crossmatch_cat.fits"))
        return sn.all([
            super().validate(),
            test_fits[1].data.shape[0] > 0
        ])

