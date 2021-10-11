#! /usr/bin/env bash

#  * Copyright (c) 2020-2021. Authors: see NOTICE file.
#  *
#  * Licensed under the GNU Lesser General Public License, Version 2.1 (the "License");
#  * you may not use this file except in compliance with the License.
#  * You may obtain a copy of the License at
#  *
#  *      https://www.gnu.org/licenses/lgpl-2.1.txt
#  *
#  * Unless required by applicable law or agreed to in writing, software
#  * distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

# Prerequisites to install before installing the plugin itself.

# How to run this script ?
# bash install-prerequisites.sh func arg1 arg2
# Example: bash install-prerequisites.sh dependencies_before_vips

PLUGIN_NAME="pims-plugin-format-bioformats"

dependencies_before_vips() {
  echo "Prerequisites to install before vips for ${PLUGIN_NAME}";
}

dependencies_before_python() {
  echo "Prerequisites to install before Python dependencies for ${PLUGIN_NAME}";
}

# Check if the function exists
if declare -f "$1" > /dev/null
then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi