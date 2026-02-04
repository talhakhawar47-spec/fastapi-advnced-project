import os
from dotenv import load_dotenv
from imagekitio import ImageKit

load_dotenv()

PRIVATE_KEY = os.getenv("IMAGEKIT_PRIVATE_KEY")

if not PRIVATE_KEY:
    raise ValueError("Missing IMAGEKIT_PRIVATE_KEY in .env")

# The ImageKit SDK (v5.1.0) expects private_key and optionally base_url.
# For uploads, it's safer to use the dedicated upload endpoint.
imagekit = ImageKit(
    private_key=PRIVATE_KEY,
    base_url="https://upload.imagekit.io"
)

def upload_image(file_path: str, file_name: str = None, use_unique_file_name: bool = True):
    """
    Upload an image/video to ImageKit.
    Returns: dict response from ImageKit
    """
    if not file_name:
        file_name = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        upload_options = {
            "file": f,
            "file_name": file_name,
            "use_unique_file_name": use_unique_file_name,
            "tags": ["backend-upload"]
        }
        result = imagekit.files.upload(**upload_options)
    return result


def build_image_url(path: str, transformations: list = None):
    """
    Generate a URL for an image stored in ImageKit.
    """
    url_options = {}
    if transformations:
        url_options["transformation"] = transformations
    if URL_ENDPOINT:
        url_options["url_endpoint"] = URL_ENDPOINT
    

    return imagekit.helper.build_url(src=path, **url_options)
