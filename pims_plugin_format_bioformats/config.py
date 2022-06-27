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

import os
from functools import lru_cache

from pydantic import BaseSettings


class Settings(BaseSettings):
    bioformats_host = "bioformat"
    bioformats_port = 4321
    bioformats_metadata_timeout = 15
    bioformats_conversion_timeout = 200 * 60

    class Config:
        env_file = "pims-config.env"
        env_file_encoding = 'utf-8'


@lru_cache()
def get_settings():
    env_file = os.getenv('CONFIG_FILE', 'pims-config.env')
    return Settings(_env_file=env_file)
