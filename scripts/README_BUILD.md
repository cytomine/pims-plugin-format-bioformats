# PIMS Isyntax plugin - Build & Continous integration

## Jenkins file

A `Jenkinsfile` is located at the root of the directory.
Build steps:
* Clean `./ci` directory ; In this directory we will store all temp data for the build.
* Get the current version (see Versionning section)
* Create a Docker image with all dependencies
* Run tests

The `scripts/ciBuildLocal.sh` contains same steps as Jenkinsfile but can be run without Jenkins.

## Tests

Tests are run with pytest.
The test report is extracted as a XML file in `ci/test-reports`

## Final build

No final build, as the source code on the repo is enough.

## Versioning

The release version is currently not supported.
Multiple possibilities:
* Manually manage version in `__version__.py` file
* Each build with an official release (x.y.z) could automatically modify the source code on the repository to update the version.
* Each build export a zip file of the code with the updated version that could be stored somewhere.