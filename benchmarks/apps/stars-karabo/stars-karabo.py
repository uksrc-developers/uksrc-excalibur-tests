import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest


class STARSkarabo_base(STARSTest):
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/karabo"
    container_url = container_image

    container_precmd += "/scripts/get-data.sh\n"

    container_cmd = "/scripts/run-task.sh"
    execute_script = container_cmd

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        return sn.all([
            super().validate(),
        ])

@rfm.simple_test
class STARSkarabo_sim(STARSkarabo_base):
    stars_name="karabo_sim"
    dataset = [
        {"filename": "Combined_input_catalogue_alpha.fits", "url": "https://lofar-surveys.org/public/Combined_input_catalogue_alpha.fits"},
    ]
    env_variables["STEP"] = "sim"
    reference_time = 10.33

@rfm.simple_test
class STARSkarabo_clean(STARSkarabo_base):
    stars_name="karabo_clean"
    dataset = [
        {"filename": "mwa-ph1-10x8s-16x80khz.zip", "url": "https://projects.pawsey.org.au/srcnet/mwa-ph1-10x8s-16x80khz.zip", "decompress":"unzip"},
    ]
    env_variables["STEP"] = "clean"
    reference_time = 52.0

@rfm.simple_test
class STARSkarabo_source_find(STARSkarabo_base):
    stars_name="karabo_source_find"
    dataset = [
        {"filename": "mwa-ph1-10x8s-16x80khz.zip", "url": "https://projects.pawsey.org.au/srcnet/mwa-ph1-10x8s-16x80khz.zip", "decompress":"unzip"},
        {"filename": "GGSM_updated.fits", "url": "https://github.com/GLEAM-X/GLEAM-X-pipeline/raw/master/models/GGSM_updated.fits"},
        {"filename": "wsclean_mwa-ph1-10x8s-16x80khz-image.fits", "url": "https://projects.pawsey.org.au/srcnet/wsclean_mwa-ph1-10x8s-16x80khz-image.fits"},
    ]
    env_variables["STEP"] = "source-find"
    reference_time = 24.67
