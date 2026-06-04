import os

import reframe as rfm
from reframe.core.builtins import sanity_function

from benchmarks.modules.utils import STARSTest

from astropy.io import fits

@rfm.simple_test
class STARSpulsarsearchpresto(STARSTest):
    stars_name="pulsarsearchpresto"
    container_url = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/pulsar-search-presto"
    cpus_per_task = parameter([16])

    # dataset is a list of dicts with "filename" and "url" fields
    dataset = [{"filename":"splice_0001.fits", "url":"https://zenodo.org/records/10989783/files/splice_0001.fits?download=1"}]
    env = 'DATA=big'

    @sanity_function
    def validate(self):
        return True

