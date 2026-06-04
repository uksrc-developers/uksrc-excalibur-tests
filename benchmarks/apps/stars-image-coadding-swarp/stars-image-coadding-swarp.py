import os

import reframe as rfm
from reframe.core.builtins import sanity_function

from benchmarks.modules.utils import STARSTest

from astropy.io import fits

@rfm.simple_test
class STARSimagecoaddingswarp(STARSTest):
    stars_name="imagecoaddingswarp"
    container_url = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/image-coadding-swarp"
    cpus_per_task = parameter([1])

    # dataset is a list of dicts with "filename" and "url" fields
    dataset = [{"filename":"frame-r-006174-2-0094.fits.bz2", "url":"http://dr17.sdss.org/sas/dr17/eboss/photoObj/frames/301/6174/2/frame-r-006174-2-0094.fits.bz2", "decompress":"bzip2"},
               {"filename":"frame-r-000756-5-0595.fits.bz2", "url":"http://dr17.sdss.org/sas/dr17/eboss/photoObj/frames/301/756/5/frame-r-000756-5-0595.fits.bz2", "decompress":"bzip2"},
               {"filename":"frame-r-001233-5-0038.fits.bz2", "url":"http://dr17.sdss.org/sas/dr17/eboss/photoObj/frames/301/1233/5/frame-r-001233-5-0038.fits.bz2", "decompress":"bzip2"},
               {"filename":"frame-r-001334-5-0056.fits.bz2", "url":"http://dr17.sdss.org/sas/dr17/eboss/photoObj/frames/301/1334/5/frame-r-001334-5-0056.fits.bz2", "decompress":"bzip2"}]

    execute_script = "/scripts/coadd-sdss.sh"

    @sanity_function
    def validate(self):
        test_fits = fits.open(os.path.join(self.data_dir, "coadd.fits"))
        return test_fits[1].data.shape[0] > 0

