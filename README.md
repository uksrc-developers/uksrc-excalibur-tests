[![DOI](https://zenodo.org/badge/381099159.svg)](https://zenodo.org/doi/10.5281/zenodo.11144871)

# UKSRC Fork 

This repository is a fork of the [UKRI excalibur-tests](https://github.com/ukri-excalibur/excalibur-tests) repository. 
As such, most of the work in this repository is solely the work of the contributors to the original repository. This 
fork serves to implement additional local spack repositories and apps for testing UK Square-Kilometre Array (SKA) 
Regional Center (UKSRC) hardware with synthetic benchmarks and testing workflows through micro-benchmarks.

In order to use this repository, it is generally advised to follow the 
[Installation](https://ukri-excalibur.github.io/excalibur-tests/install) and 
[Setup](https://ukri-excalibur.github.io/excalibur-tests/setup/) instructions.

In brief, here is the recommended steps, details can be found in the previously mentioned links.

## Repo and spack
<details>
<summary>Installing</summary>

### For the Repository and ReFrame
* Clone Repository
* `cd ukserc-excalibur-tests`
* `pip install -e ./`
* `export RFM_CONFIG_FILES=</path/to/framework>/benchmarks/reframe_config.py`
  * This needs to go into the configuration file (e.g. ~/.bashrc).
  * This serves to tell ReFrame where the config file is.
* `export RFM_USE_LOGIN_SHELL="true"`
  * This needs to go into the configuration file (e.g. ~/.bashrc) .
  * This serves to let ReFrame know to use the configuration file used for the login node (e.g. ~/.bashrc).

### Spack
* `git clone -c feature.manyFiles=true --depth=2 https://github.com/spack/spack.git --branch v1.0.0`
* `source ./spack/share/spack/setup-env.sh`
  * This needs to go into the configuration file (e.g. ~/.bashrc) 
* `spack --version`
  * To verify the spack installation

### Spack Environment
ReFrame needs a spack environment it can reference to, so we create a new spack environment.
* `spack env create --without-view -d </chosen/path/to/spack/env/>`
* `spack env activate </chosen/path/to/spack/env/>`
  * This needs to go into the configuration file (e.g. ~/.bashrc).
* `spack config add 'config:install_tree:root:$env/opt/spack'`
* `export EXCALIBUR_SPACK_ENV=</chosen/path/to/spack/env/>`
  * This needs to go into the configuration file (e.g. ~/.bashrc).
  * This lets the ExCALIBUR tests software know which spack environment to use.
* `spack compiler find`
  * This searches for compilers on the current system so spack can use them.
* `spack external find`
  * This searches for already installed packages, and adds them to the environment.
  * In cases where modules are loaded, load them prior to using this command.
  * It may be useful to look at the [documentation for package settings](https://spack.readthedocs.io/en/latest/packages_yaml.html)
* `spack -e </chosen/path/to/spack/env/> repo add </path/to/framework>/benchmarks/spack/repo`
  * This links the environment to a local spack package repository that can be modified.
</details>

<details>
<summary>Adding benchmarks</summary>


In order to add a benchmark to this testing framework, two things need to be done. 

First, it is necessary to verify the existence of the benchmark in the [spack package repo](https://packages.spack.io/), 
or create the spack package following the 
[spack package creation tutorial](https://spack-tutorial.readthedocs.io/en/latest/tutorial_packaging.html). If the 
package needs to be created, it can be added to the `<repo>/benchmarks/spack/repo/packages` directory which is the local 
spack repo that the spack environment should be set up to have access to, or it can be uploaded to the spack package 
repository. If needed, an example package can be found in `<repo>/benchmarks/spack/repo/packages/example`. 
In either situation, installing a package can be done with `spack install --add <name-of-package>`. 

Second, the test needs to be added to benchmarks directory `<repo>/benchmarks/apps/<test_name>`. This can be done by 
following the [ReFrame Tutorial](https://reframe-hpc.readthedocs.io/en/stable/tutorial.html) for creating a test. As 
was the case for spack packages, an example of two tests can be found in `<repo>/examples/` where both sombrero and 
stream can serve as good starting points for adding a package.

For additional reference, the fft-bench package was created for this project following the above mentioned tutorials
and example files.
</details>

# ExCALIBUR tests
<details>
<summary>Original branch ReadMe</summary>
Performance benchmarks and regression tests for the ExCALIBUR project.

These benchmarks are based on a similar project by
[StackHPC](https://github.com/stackhpc/hpc-tests).

Feel free to add new benchmark applications or support new systems that are part of the
ExCALIBUR benchmarking collaboration.

_**Note**: at the moment the ExCALIBUR benchmarks are a work-in-progress._

## Documentation

- [Installation](https://ukri-excalibur.github.io/excalibur-tests/install/)
- [Configuration](https://ukri-excalibur.github.io/excalibur-tests/setup/)
- [Usage](https://ukri-excalibur.github.io/excalibur-tests/use/)
- [Post-processing](https://ukri-excalibur.github.io/excalibur-tests/post-processing/)
- [Contributing](https://ukri-excalibur.github.io/excalibur-tests/contributing/)
- [Supported benchmarks](https://ukri-excalibur.github.io/excalibur-tests/apps/)
- [Supported systems](https://ukri-excalibur.github.io/excalibur-tests/systems/)
- [ReFrame tutorial](https://ukri-excalibur.github.io/excalibur-tests/tutorial/reframe_tutorial/)
- [ARCHER2 tutorial](https://ukri-excalibur.github.io/excalibur-tests/tutorial/archer2_tutorial/)


</details>

## Acknowledgements

This work was supported by the Engineering and Physical Sciences
Research Council [EP/X031829/1].

This work used the DiRAC@Durham facility managed by the Institute for Computational 
Cosmology on behalf of the STFC DiRAC HPC Facility (www.dirac.ac.uk). The equipment 
was funded by BEIS capital funding via STFC capital grants ST/P002293/1, ST/R002371/1
and ST/S002502/1, Durham University and STFC operations grant ST/R000832/1. 
DiRAC is part of the National e-Infrastructure.

The main outcomes of this work were published in a [paper](https://dl.acm.org/doi/10.1145/3624062.3624133) in the HPCTESTS workshop in SC23.

This work was [presented in RSECon23](https://virtual.oxfordabstracts.com/#/event/4430/submission/74). A [recording of the talk](https://youtu.be/vpTD_tJqWOA?si=zl9sWvPEQYyPhJTV) is available.
