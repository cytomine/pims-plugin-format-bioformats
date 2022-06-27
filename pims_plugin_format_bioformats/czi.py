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

from pims.cache import cached_property

from pims.formats import AbstractFormat
from pims.formats.utils.abstract import CachedDataPath
from pims.formats.utils.checker import SignatureChecker
from pims.formats.utils.histogram import DefaultHistogramReader
from pims_plugin_format_bioformats.utils.engine import (
    BioFormatsParser, BioFormatsReader,
    BioFormatsSpatialConvertor
)

CZI_SIGNATURE = bytearray("ZISRAWFILE".encode("utf8"))


class CZIChecker(SignatureChecker):
    @classmethod
    def match(cls, pathlike: CachedDataPath) -> bool:
        buf = cls.get_signature(pathlike)
        return len(buf) > 10 and buf[:10] == CZI_SIGNATURE


class CZIFormat(AbstractFormat):
    """
    Zeiss CZI format.

    Known limitations:
    *

    References:
    * https://github.com/ome/bioformats/blob/develop/components/formats-gpl/src/loci/formats/in/ZeissCZIReader.java
    * https://docs.openmicroscopy.org/bio-formats/6.7.0/formats/zeiss-czi.html
    * https://github.com/zeiss-microscopy/libCZI

    """
    checker_class = CZIChecker
    parser_class = BioFormatsParser
    reader_class = None
    histogram_reader_class = DefaultHistogramReader
    convertor_class = BioFormatsSpatialConvertor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._enabled = True

    @classmethod
    def get_name(cls):
        return "Zeiss CZI"

    @classmethod
    def is_spatial(cls):
        return True

    @cached_property
    def need_conversion(self):
        return True
