#!/bin/bash

set -o xtrace
set -o errexit

echo "************************************** Launch tests ******************************************"

file='./ci/version'
VERSION_NUMBER=$(<"$file")

echo "Launch tests for $VERSION_NUMBER"
mkdir "$PWD"/ci/test-reports
touch "$PWD"/ci/test-reports/pytest_unit.xml
docker build --rm -f scripts/docker/Dockerfile-test --build-arg VERSION_NUMBER=$VERSION_NUMBER -t  cytomine/pims-plugin-format-bioformats-test .

containerIdBioformat=$(docker create --name bioformat -v /data/images:/data/images -v /data/pims:/data/pims -e BIOFORMAT_PORT=4321 --restart=unless-stopped cytomine/bioformat:v3.1.0 )
docker start $containerIdBioformat

containerId=$(docker create --link bioformat:bioformat -v /data/pims:/data/pims -v "$PWD"/ci/test-reports:/app/ci/test-reports -v /tmp/uploaded:/tmp/uploaded -v /tmp/test-pims:/tmp/test-pims cytomine/pims-plugin-format-bioformats-test )

docker start -ai  $containerId
docker rm $containerId
docker stop $containerIdBioformat
docker rm $containerIdBioformat
