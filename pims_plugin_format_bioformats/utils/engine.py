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
from __future__ import annotations

import json
import logging
import select
from socket import AF_INET, SOCK_STREAM, error as socket_error, socket
from typing import Optional, TYPE_CHECKING

import numpy as np
from asgiref.sync import async_to_sync
from fastapi_cache.coder import PickleCoder
from pint import Quantity

from pims import UNIT_REGISTRY
from pims.cache import cache
from pims.formats import AbstractFormat
from pims.formats.utils.convertor import AbstractConvertor
from pims.formats.utils.parser import AbstractParser
from pims.formats.utils.reader import AbstractReader
from pims.formats.utils.structures.metadata import ImageChannel, ImageMetadata, MetadataStore
from pims.formats.utils.structures.planes import PlanesInfo
from pims.formats.utils.structures.pyramid import Pyramid, normalized_pyramid
from pims.utils.color import Color
from pims.utils.types import parse_float
from pims_plugin_format_bioformats.config import get_settings

if TYPE_CHECKING:
    from pims.files.file import Path

settings = get_settings()

logger = logging.getLogger("pims.formats")


def ask_bioformats(
    message: dict,
    request_timeout: float = 1.0,
    response_timeout: float = 15.0,
    silent_fail: bool = False
) -> dict:
    request = json.dumps(message) + "\n"

    response = ""
    try:
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.settimeout(request_timeout)
            sock.connect((settings.bioformats_host, settings.bioformats_port))
            sock.sendall(request.encode('utf-8'))
            closed = False
            _response_timeout = response_timeout

            def _data_available():
                if closed:
                    return False
                try:
                    return bool(select.select([sock], [], [], _response_timeout)[0])
                except socket_error:
                    raise InterruptedError

            buffer_size = 4096
            while _data_available():
                _response_timeout = 0.5
                data = sock.recv(buffer_size)
                if data:
                    response += data.decode('utf-8')

                if not data or len(data) < buffer_size:
                    closed = True
                    break

            parsed_response = json.loads(response)
            if not silent_fail and 'error' in parsed_response:
                raise ValueError  # TODO: better error

            return parsed_response
    except InterruptedError as e:
        logger.error(f"Connection to Bio-Formats ({settings.bioformats_host}:"
                     f"{settings.bioformats_port} has failed or has been interrupted.")
        raise e
    except TimeoutError:
        logger.error(f"Timeout error ({response_timeout} s) while waiting Bio-Formats "
                     f"response for message: {message}")


@async_to_sync
@cache(codec=PickleCoder)
def _bioformats_metadata(path: Path) -> dict:
    message = {
        "action": "properties",
        "includeRawProperties": False,
        "legacyMode": False,
        "path": str(path)
    }
    return ask_bioformats(message)


def cached_bioformats_metadata(format: AbstractFormat) -> dict:
    return format.get_cached(
        '_bioformats_md', _bioformats_metadata, format.path.resolve()
    )


class BioFormatsParser(AbstractParser):
    def parse_main_metadata(self) -> ImageMetadata:
        metadata = cached_bioformats_metadata(self.format)

        imd = ImageMetadata()
        imd.width = metadata.get('Bioformats.Pixels.SizeX')
        imd.height = metadata.get('Bioformats.Pixels.SizeY')
        imd.n_channels = metadata.get('Bioformats.Pixels.SizeC')
        imd.depth = metadata.get('Bioformats.Pixels.SizeZ')
        imd.duration = metadata.get('Bioformats.Pixels.SizeT')
        imd.n_intrinsic_channels = metadata.get('Bioformats.Pixels.EffectiveSizeC')
        imd.n_channels_per_read = imd.n_channels / imd.n_intrinsic_channels

        imd.pixel_type = metadata.get('Bioformats.Pixels.PixelType')
        imd.significant_bits = metadata.get('Bioformats.Pixels.BitsPerPixel')

        for i, channel_md in enumerate(metadata.get('Bioformats.Channels')):
            color = None
            if channel_md.get('Color') is not None:
                color = Color(channel_md.get('Color'))

            emission = self.parse_physical_size(
                channel_md.get('EmissionWavelength'),
                channel_md.get('EmissionWavelengthUnit')
            )

            excitation = self.parse_physical_size(
                channel_md.get('ExcitationWavelength'),
                channel_md.get('ExcitationWavelengthUnit')
            )

            imd.set_channel(
                ImageChannel(
                    index=i,
                    emission_wavelength=emission,
                    excitation_wavelength=excitation,
                    suggested_name=channel_md.get('SuggestedName'),
                    color=color
                )
            )

        return imd

    def parse_known_metadata(self) -> ImageMetadata:
        imd = super().parse_known_metadata()
        metadata = cached_bioformats_metadata(self.format)

        imd.acquisition_datetime = metadata.get('Bioformats.Image.AcquisitionDate')
        imd.description = metadata.get('Bioformats.Image.Description')

        imd.physical_size_x = self.parse_physical_size(
            metadata.get('Bioformats.Pixels.PhysicalSizeX'),
            metadata.get('Bioformats.Pixels.PhysicalSizeXUnit')
        )

        imd.physical_size_y = self.parse_physical_size(
            metadata.get('Bioformats.Pixels.PhysicalSizeY'),
            metadata.get('Bioformats.Pixels.PhysicalSizeYUnit')
        )

        imd.physical_size_z = self.parse_physical_size(
            metadata.get('Bioformats.Pixels.PhysicalSizeZ'),
            metadata.get('Bioformats.Pixels.PhysicalSizeZUnit')
        )

        imd.frame_rate = self.parse_physical_size(
            metadata.get('Bioformats.Pixels.TimeIncrement'),
            metadata.get('Bioformats.Pixels.TimeIncrementUnit')
        )

        imd.objective.nominal_magnification = parse_float(
            metadata.get('Bioformats.Objective.NominalMagnification')
        )

        imd.objective.calibrated_magnification = parse_float(
            metadata.get('Bioformats.Objective.CalibratedMagnification')
        )

        imd.microscope.model = metadata.get('Bioformats.Microscope.Model')

        for associated in ('Macro', 'Thumb', 'Label'):
            key = f'Bioformats.Series.{associated}'
            if associated in metadata:
                imd_associated = getattr(imd, f'associated_{associated.lower()}')
                imd_associated.width = metadata[key].get('Width')
                imd_associated.height = metadata[key].get('Height')
                imd_associated.n_channels = metadata[key].get('Channels')
        imd.is_complete = True
        return imd

    @staticmethod
    def parse_physical_size(
        physical_size: Optional[str], unit: Optional[str]
    ) -> Optional[Quantity]:
        if physical_size is not None \
                and parse_float(physical_size) is not None \
                and unit is not None:
            return parse_float(physical_size) * UNIT_REGISTRY(unit)
        return None

    def parse_pyramid(self) -> Pyramid:
        metadata = cached_bioformats_metadata(self.format)

        pyramid = Pyramid()
        for tier in metadata.get('Bioformats.Pyramid', []):
            pyramid.insert_tier(
                width=tier.get('Width'),
                height=tier.get('Height'),
                tile_size=(tier.get('TileWidth'), tier.get('TileHeight'))
            )

        return pyramid

    def parse_planes(self) -> PlanesInfo:
        metadata = cached_bioformats_metadata(self.format)
        imd = self.format.main_imd
        planes = PlanesInfo(
            imd.n_intrinsic_channels, imd.depth, imd.duration,
            ['bf_index', 'bf_series'], [np.int, np.int]
        )

        for plane_info in metadata.get('Bioformats.Planes', []):
            c = plane_info.get('TheC')
            z = plane_info.get('TheZ')
            t = plane_info.get('TheT')
            planes.set(
                c, z, t,
                bf_index=plane_info.get('_Index'),
                bf_series=plane_info.get('_Series')
            )

        return planes

    def parse_raw_metadata(self) -> MetadataStore:
        message = {
            "action": "properties",
            "includeRawProperties": True,
            "legacyMode": False,
            "path": str(self.format.path)
        }
        raw_metadata = ask_bioformats(message)

        store = super().parse_raw_metadata()
        for key, value in raw_metadata.items():
            store.set(key, value)
        return store


# TODO
class BioFormatsReader(AbstractReader):
    def read_thumb(self, out_width, out_height, precomputed=None, c=None, z=None, t=None):
        raise NotImplementedError

    def read_window(self, region, out_width, out_height, c=None, z=None, t=None):
        raise NotImplementedError

    def read_tile(self, tile, c=None, z=None, t=None):
        raise NotImplementedError


class BioFormatsSpatialConvertor(AbstractConvertor):
    def convert(self, dest_path: Path) -> bool:
        width = self.source.main_imd.width
        height = self.source.main_imd.height
        n_resolutions = normalized_pyramid(width, height).n_levels
        message = {
            "action": "convert",
            "legacyMode": False,
            "path": str(self.source.path),
            "output": str(dest_path),
            "onlyBiggestSerie": True,  # TODO: need to convert series corresponding to associated
            "flatten": False,
            "compression": "LZW",
            "keepOriginalMetadata": False,
            "group": True,
            "nPyramidResolutions": n_resolutions,
            "pyramidScaleFactor": 2
        }
        result = ask_bioformats(message, response_timeout=1800.0, silent_fail=True)
        return 'file' in result

    def conversion_format(self):
        from pims.formats.common.ometiff import OmeTiffFormat
        return OmeTiffFormat
