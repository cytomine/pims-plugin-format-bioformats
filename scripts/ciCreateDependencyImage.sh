#!/bin/bash

set -o xtrace
set -o errexit

echo "************************************** Create dependency image ******************************************"

file='./ci/version'
VERSION_NUMBER=$(<"$file")

echo "Launch Create dependency image for $VERSION_NUMBER"

git clone --branch master --depth 1 https://github.com/cytomine/pims ./ci/app

mkdir -p ./ci/app/plugins/pims-plugin-format-bioformats/
cp -r ./pims_plugin_format_bioformats ./ci/app/plugins/pims-plugin-format-bioformats/
#cp -r ./pims_plugin_format_bioformats.egg-info ./ci/app/plugins/pims-plugin-format-bioformats/
cp -r ./tests ./ci/app/plugins/pims-plugin-format-bioformats/
cp ./setup.py ./ci/app/plugins/pims-plugin-format-bioformats/

#git clone https://github.com/cytomine/pims-plugin-format-openslide ./ci/app/plugins/pims-plugin-format-openslide

docker build --rm -f scripts/docker/Dockerfile-dependencies -t  cytomine/pims-plugin-format-bioformats-dependencies:v$VERSION_NUMBER .
