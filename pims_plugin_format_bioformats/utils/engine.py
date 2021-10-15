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

import json
import logging
from socket import AF_INET, SOCK_STREAM, socket

from asgiref.sync import async_to_sync
from fastapi_cache.coder import PickleCoder
from pims import UNIT_REGISTRY
from pims.cache import cache
from pims.formats.utils.abstract import AbstractConvertor, AbstractParser, AbstractReader
from pims.formats.utils.metadata import ImageChannel, ImageMetadata, parse_float
from pims.formats.utils.pyramid import normalized_pyramid
from pims.processing.color import Color

from pims_plugin_format_bioformats.config import get_settings

settings = get_settings()

logger = logging.getLogger("pims.formats")


def ask_bioformats(message: dict, timeout: float = 15.0, silent_fail: bool = False) -> dict:
    request = json.dumps(message) + "\n"

    response = ""
    try:
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((settings.bioformats_host, settings.bioformats_port))
            sock.sendall(request.encode('utf-8'))

            buffer_size = 1024
            while True:
                data = sock.recv(buffer_size)
                response += data.decode('utf-8')
                if len(data) < buffer_size:
                    break

            parsed_response = json.loads(response)
            if not silent_fail and 'error' in parsed_response:
                raise ValueError  # TODO: better error

            return parsed_response
    except InterruptedError as e:
        logger.error(f"Connection to Bio-Formats ({settings.bioformats_host}:"
                     f"{settings.bioformats_port} has failed or has been interrupted.")
        raise e
    except TimeoutError as e:
        logger.error(f"Timeout error ({timeout} s) while waiting Bio-Formats "
                     f"response for message: {message}")


@async_to_sync
@cache(codec=PickleCoder)
def _bioformats_metadata(path):
    message = {
        "action": "properties",
        "includeRawProperties": False,
        "legacyMode": False,
        "path": str(path)
    }
    return ask_bioformats(message)


def cached_bioformats_metadata(format):
    return format.get_cached('_bioformats_md', _bioformats_metadata, format.path.resolve())


class BioFormatsParser(AbstractParser):
    def parse_main_metadata(self):
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

            imd.set_channel(ImageChannel(
                index=i,
                suggested_name=channel_md.get('SuggestedName'),
                emission_wavelength=emission,
                excitation_wavelength=excitation,
                color=color
            ))

        return imd

    def parse_known_metadata(self):
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

        # TODO
        # for associated in ('macro', 'thumbnail', 'label'):
        #     if associated in get_vips_field(image, 'slide-associated-images', []):
        #         head = VIPSImage.openslideload(
        #             str(self.format.path), associated=associated
        #         )
        #         imd_associated = getattr(imd, f'associated_{associated[:5]}')
        #         imd_associated.width = head.width
        #         imd_associated.height = head.height
        #         imd_associated.n_channels = head.bands
        imd.is_complete = True
        return imd

    @staticmethod
    def parse_physical_size(physical_size, unit):
        if physical_size is not None \
                and parse_float(physical_size) is not None \
                and unit is not None:
            return parse_float(physical_size) * UNIT_REGISTRY(unit)
        return None

    def parse_raw_metadata(self):
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
    def convert(self, dest_path):
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
        result = ask_bioformats(message, timeout=1800.0, silent_fail=True)
        return 'file' in result

    def conversion_format(self):
        from pims.formats.common.ometiff import OmeTiffFormat
        return OmeTiffFormat
