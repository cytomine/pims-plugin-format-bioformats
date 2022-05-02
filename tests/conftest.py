#  * Copyright (c) 2020-2021. Authors: see NOTICE file.
#  *
#  * Licensed under the Apache License, Version 2.0 (the "License");
#  * you may not use this file except in compliance with the License.
#  * You may obtain a copy of the License at
#  *
#  *      http://www.apache.org/licenses/LICENSE-2.0
#  *
#  * Unless required by applicable law or agreed to in writing, software
#  * distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pims import config

os.environ['CONFIG_FILE'] = "./pims-config.env"

def get_test_root():
    return get_settings().root
    
@pytest.fixture
def root():
    return get_test_root()


def get_settings():
    return config.Settings(
        _env_file=os.getenv("CONFIG_FILE")
    )
"""
def get_pims_root():
    print(get_settings())
    return get_settings().root_pims

@pytest.fixture 
def pims_root():
    return get_pims_root()
"""
@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def app():
    from pims import application as main

    main.app.dependency_overrides[config.get_settings] = get_settings
    return main.app


@pytest.fixture
def client(app):
    return TestClient(app)

@pytest.fixture
def image_path_czi():
	path = f"{get_test_root()}/upload_test_bioformats_czi"
	filename = "Plate1-Blue-A-12-Scene-3-P3-F2-03.czi"
	return [path, filename]
	
@pytest.fixture
def image_path_nd2():
	path = f"{get_test_root()}/upload_test_bioformats_nd2"
	filename = "BF007.nd2"
	return [path, filename]
	
@contextmanager
def not_raises(expected_exc):
    try:
        yield

    except expected_exc as err:
        raise AssertionError(
            "Did raise exception {0} when it should not!".format(
                repr(expected_exc)
            )
        )

    except Exception as err:
        raise AssertionError(
            "An unexpected exception {0} raised.".format(repr(err))
        )
