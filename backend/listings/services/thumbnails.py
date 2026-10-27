from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def make_thumbnail(source) -> ContentFile:
    """Builds a WEBP preview of a validated photo: its longer side is THUMBNAIL_SIZE px at most."""
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original)  # a copy, turned the way the camera meant it
    image.thumbnail((settings.THUMBNAIL_SIZE, settings.THUMBNAIL_SIZE))  # keeps proportions, never enlarges
    buffer = BytesIO()
    image.save(buffer, format='WEBP', quality=80)
    return ContentFile(buffer.getvalue())
