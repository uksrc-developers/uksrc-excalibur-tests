import os

import reframe as rfm
from reframe.core.builtins import sanity_function
import reframe.utility.sanity as sn

from benchmarks.modules.utils import STARSTest

from astropy.io import fits

@rfm.simple_test
class STARSimageconvolution(STARSTest):
    stars_name="imageconvolution"
    tags = {"stars"}
    container_image = "docker://registry.gitlab.com/ska-telescope/src/src-workloads/image-convolution"
    container_url = container_image
    cpus_per_task = parameter([4])

    #data_base_url = "https://lofar-surveys.org/public/DR2/mosaics"
    #data_base_filename = "mosaic-blanked.fits"

    # This is the 100 images dataset
    #images = "P000+23 P000+31 P000+36 P000+38 P001+26 P001+33 P001+41 P002+18 P002+21 P002+23 P002+28 P003+31 P003+36 P004+18 P004+26 P004+33 P004+38 P004+41 P005+21 P005+23 P005+28 P006+31 P006+36 P007+18 P007+21 P007+26 P007+33 P007+39 P007+41 P008+23 P008+28 P009+31 P009+36 P010+18 P010+21 P010+26 P010+34 P010+39 P011+23 P011+29 P011+41 P012+31 P012+36 P013+18 P013+21 P013+26 P013+34 P014+24 P014+29 P014+39 P014+41 P015+19 P015+31 P016+21 P016+24 P016+26 P016+34 P016+36 P017+29 P017+39 P018+19 P018+21 P018+31 P018+41 P019+24 P019+26 P019+34 P019+36 P020+29 P020+39 P000+23 P000+31 P000+36 P000+38 P001+26 P001+33 P001+41 P002+18 P002+21 P002+23 P002+28 P003+31 P003+36 P004+18 P004+26 P004+33 P004+38 P004+41 P005+21 P005+23 P005+28 P006+31 P006+36 P007+18 P007+21 P007+26 P007+33 P007+39 P007+41 P008+23 P008+28 P009+31 P009+36 P010+18 P010+21 P010+26 P010+34 P010+39 P011+23 P011+29 P011+41 P012+31 P012+36 P013+18 P013+21 P013+26 P013+34 P014+24 P014+29 P014+39 P014+41 P015+19 P015+31 P016+21 P016+24 P016+26 P016+34 P016+36 P017+29 P017+39 P018+19 P018+21 P018+31 P018+41 P019+24 P019+26 P019+34 P019+36 P020+29 P020+39 P021+19 P021+21 P021+26 P021+31 P021+41 P022+24 P022+34 P022+36 P023+29 P024+19 P024+21 P024+26 P024+31 P024+39 P025+24 P025+36 P025+41 P026+19 P026+29 P026+34 P027+21 P027+26 P027+31 P027+39 P028+24 P028+36 P028+41 P029+19 P029+29 P029+34".split()

    images = "P007+39.fits"

    dataset=[{"url":f"https://lofar-surveys.org/public/DR2/mosaics/P007+39/mosaic-blanked.fits", "filename":f"P007+39.fits"}]
    env_variables["DATA"] = '1image'

    reference_time = 30.0

    @sanity_function
    def validate(self):
        if getattr(self.current_partition.scheduler, 'container_scheduler', False):
            return super().validate()
        test_fits = fits.open(os.path.join(self.data_dir, "output/conv_P007+39.fits"))
        return sn.all([
            super().validate(),
            test_fits[0].data.shape[0] > 0
        ])

