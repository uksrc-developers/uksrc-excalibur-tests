import os


import reframe as rfm
from reframe.core.builtins import sanity_function

from benchmarks.modules.utils import STARSTest

from astropy.io import fits

@rfm.simple_test
class STARScrossmatch(STARSTest):
    bench_name="STARScrossmatch"
    container_url = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/cross-matching"

    @sanity_function
    def validate(self):
        test_fits = fits.open(os.path.join(self.data_dir, "crossmatch_cat.fits"))
        return test_fits[1].data.shape[0] > 0

