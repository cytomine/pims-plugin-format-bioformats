from PIL import Image
import os, io, json
import urllib.request
from fastapi import APIRouter
from pims.formats import FORMATS
from pims.importer.importer import FileImporter

from pims.files.file import (ORIGINAL_STEM, Path, SPATIAL_STEM, HISTOGRAM_STEM)

from pims.api.utils.models import HistogramType
from pims.processing.histograms.utils import build_histogram_file
from pims.formats.utils.factories import FormatFactory
from pims.utils.dtypes import dtype_to_bits
import pytest
import subprocess
from subprocess import Popen, PIPE, STDOUT

def get_image(root, path, filename):
    filepath = os.path.join(path, filename)
    # If image does not exist locally -> download image
    
    if not os.path.exists("/tmp/images"):
        os.mkdir("/tmp/images")

    if not os.path.exists(root):
        os.mkdir(root)
	 
    if not os.path.exists(f"/tmp/images/{filename}"):
        try:
            url = f"https://downloads.openmicroscopy.org/images/Zeiss-CZI/idr0011/Plate1-Blue-A_TS-Stinger/{filename}"
            urllib.request.urlretrieve(url, f"/tmp/images/{filename}")
        except Exception as e:
            print("Could not download image")
            print(e)
    if not os.path.exists(filepath): 
        image_path = f"/tmp/images/{filename}"
        pims_root = root
        importer_path = f"/app/pims/importer/import_local_images.py" # pims folder should be in root folder
        import_img=subprocess.run(["python3", importer_path, "--path", image_path], stdout=subprocess.PIPE)
        
        subdirs = os.listdir(pims_root)
        for subdir in subdirs:
            if "upload-" in str(subdir):
                subsubdirs = os.listdir(os.path.join(root, subdir))
                for subsubdir in subsubdirs:
                    if filename in str(subsubdir):
                        upload_dir = os.path.join(root, str(subdir))
                        break
        if os.path.exists(path):
            os.unlink(path) # if the folder upload_test_bioformats_czi already exists the symlink won't work
        os.symlink(upload_dir, path)

def test_bioformats_czi_exists(image_path_czi, settings):
	# Test if the file exists, either locally either with the OAC
	path, filename = image_path_czi
	get_image(settings.root, path, filename)
	assert os.path.exists(os.path.join(path,filename)) == True

def test_format_exists(client):
    response = client.get(f'/formats')
    assert "CZI" in json.dumps(response.json())

def test_bioformats_czi_info(client, image_path_czi):
    path, filename = image_path_czi
    response = client.get(f'/image/upload_test_bioformats_czi/{filename}/info')
    assert response.status_code == 200
    assert "czi" in response.json()['image']['original_format'].lower()
    
    assert response.json()['image']['width'] == 672
    assert response.json()['image']['height'] == 512
    

def test_bioformats_czi_norm_tile(client, image_path_czi):
    _, filename = image_path_czi
    response = client.get(f"/image/upload_test_bioformats_czi/{filename}/normalized-tile/level/0/ti/0", headers={"accept": "image/jpeg"})
    assert response.status_code == 200

    img_response = Image.open(io.BytesIO(response.content))
    width_resp, height_resp = img_response.size
    assert width_resp == 256
    assert height_resp == 256

def test_bioformats_czi_thumb(client, image_path_czi):
    _, filename = image_path_czi
    response = client.get(f"/image/upload_test_bioformats_czi/{filename}/thumb", headers={"accept": "image/jpeg"})
    assert response.status_code == 200
    
    im_resp = Image.open(io.BytesIO(response.content))
    width_resp, height_resp = im_resp.size
    assert max(width_resp, height_resp) == 256
	
	
@pytest.mark.skip(reason='There is no associated macroimage')
def test_bioformats_czi_macro(client, image_path_czi):
    path, filename = image_path_czi
    response = client.get(f"/image/upload_test_bioformats_czi/{filename}/associated/macro", headers={"accept": "image/jpeg"})
    assert response.status_code == 200
    
    im_resp = Image.open(io.BytesIO(response.content))
    width_resp, height_resp = im_resp.size
    assert width_resp == 256 or height_resp == 256
    
@pytest.mark.skip(reason='There is no associated label image')
def test_bioformats_czi_label(client, image_path_czi):
    path, filename = image_path_czi
    response = client.get(f"/image/upload_test_bioformats_czi/{filename}/associated/label", headers={"accept": "image/jpeg"})
    assert response.status_code == 200
    
    im_resp = Image.open(io.BytesIO(response.content))
    width_resp, height_resp = im_resp.size
    assert width_resp == 256 or height_resp == 256
    
def test_bioformats_czi_resized(client, image_path_czi):
    _, filename = image_path_czi
    response = client.get(f"/image/upload_test_bioformats_czi/{filename}/resized", headers={"accept": "image/jpeg"})
    assert response.status_code == 200

    im_resp = Image.open(io.BytesIO(response.content))
    width_resp, height_resp = im_resp.size
    #assert width_resp == 256 or height_resp == 256
    assert max(width_resp, height_resp) == 256

def test_bioformats_czi_mask(client, image_path_czi):
    _, filename = image_path_czi
    response = client.post(f"/image/upload_test_bioformats_czi/{filename}/annotation/mask", headers={"accept": "image/jpeg"}, json={"annotations":[{"geometry": "POINT(10 10)"}], "height":50, "width":50})
    assert response.status_code == 200

def test_bioformats_czi_crop(client, image_path_czi):
    _, filename = image_path_czi
    response = client.post(f"/image/upload_test_bioformats_czi/{filename}/annotation/crop", headers={"accept": "image/jpeg"}, json={"annotations":[{"geometry": "POINT(10 10)"}], "height":50, "width":50})
    assert response.status_code == 200
    
@pytest.mark.skip(reason="Does not return the correct response code")
def test_tiff_crop_null_annot(client, image_path_czi):
    _,filename = image_path_czi
    response = client.post(f"/image/upload_test_bioformats_czi/{filename}/annotation/crop", headers={"accept": "image/jpeg"}, json={"annotations": [], "height":50, "width":50})
    assert response.status_code == 400
 

def test_bioformats_czi_histogram_perimage(client, image_path_czi):
    _, filename = image_path_czi
    response = client.get(f"/image/upload_test_bioformats_czi/{filename}/histogram/per-image", headers={"accept": "image/jpeg"})
    assert response.status_code == 200   
