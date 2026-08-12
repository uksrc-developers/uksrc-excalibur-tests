import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest

from astropy.io import fits

@rfm.simple_test
class STARSpulsarsearchpresto(STARSTest):
    stars_name="pulsarsearchpresto"
    valid_systems = ["-low_memory"]
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/pulsar-search-presto"
    cpus_per_task = parameter([16])

    # dataset is a list of dicts with "filename" and "url" fields
    dataset = [{"filename":"splice_0001.fits", "url":"https://zenodo.org/records/10989783/files/splice_0001.fits?download=1"}]
    env_variables["DATA"] = 'big'

    reference_time = 12252.0

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        return sn.all([
            super().validate(),
            os.path.isfile(os.path.join(self.data_dir,"figures/1221832280_DM16.10_ACCEL_50_ACCEL_Cand_4.pfd.png"))
        ])

