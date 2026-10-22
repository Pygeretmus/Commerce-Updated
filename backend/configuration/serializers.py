import uuid
from typing import ClassVar

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from PIL import Image
from rest_framework import serializers

User = get_user_model()


class LowerEmailField(serializers.EmailField):
    def to_internal_value(self, data):
        return super().to_internal_value(data).lower()


class ImageUploadField(serializers.ImageField):
    """
    An uploaded image: checks it and gives it a name of our own.

    The format and the size in pixels come from Pillow, which also decodes the whole file,
    so a broken or truncated upload fails here. The file keeps its content, but is renamed
    to a random name with the extension of its real format.
    Limits (IMAGE_MAX_BYTES, IMAGE_MIN_SIDE, IMAGE_MAX_SIDE) are read from the settings.
    """

    FORMATS: ClassVar[dict[str, str]] = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}

    def to_internal_value(self, data):
        file = super().to_internal_value(data)

        if file.size > settings.IMAGE_MAX_BYTES:
            limit_mb = settings.IMAGE_MAX_BYTES / (1024 * 1024)
            raise serializers.ValidationError(f'The file is too large. The limit is {limit_mb:g} MB.', 'file_too_large')

        try:
            with Image.open(file) as image:
                fmt, (width, height) = image.format, image.size
                if fmt not in self.FORMATS:
                    raise serializers.ValidationError(
                        'Unsupported image format. Use JPEG, PNG or WEBP.', 'unsupported_format'
                    )
                if min(width, height) < settings.IMAGE_MIN_SIDE:
                    raise serializers.ValidationError(
                        f'The image is too small. Each side must be at least {settings.IMAGE_MIN_SIDE} px.',
                        'dimensions_too_small',
                    )
                if max(width, height) > settings.IMAGE_MAX_SIDE:
                    raise serializers.ValidationError(
                        f'The image is too large. Each side must be at most {settings.IMAGE_MAX_SIDE} px.',
                        'dimensions_too_large',
                    )
                image.load()  # decodes every pixel, so a truncated file fails here
        except serializers.ValidationError:
            raise
        except Exception as exc:  # Pillow raises many kinds of errors on broken files
            raise serializers.ValidationError('The file is not a valid image.', 'invalid_image') from exc

        file.seek(0)
        file.name = f'{uuid.uuid4().hex}.{self.FORMATS[fmt]}'
        return file


class CustomModelSerializer(serializers.ModelSerializer):
    """
    Base serializer that automatically replaces certain model fields with
    custom serializer fields:

    - `models.EmailField` → `LowerEmailField`
    """

    serializer_field_mapping = serializers.ModelSerializer.serializer_field_mapping.copy()
    serializer_field_mapping[models.EmailField] = LowerEmailField
    serializer_field_mapping[models.ImageField] = ImageUploadField
