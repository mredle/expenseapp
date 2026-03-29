# coding=utf-8
"""Image processing pipeline: hashing, storage, thumbnail generation."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import uuid
from io import BytesIO

from PIL import Image as ImagePIL
from flask import current_app

from app import db
from app.models import File, Image, Thumbnail


def compute_file_hash(file_stream: BytesIO) -> str:
    """Compute the SHA-256 hex digest of *file_stream*.

    Reads in 8 KB chunks to keep memory usage constant on large files.
    The stream position is reset to 0 before and after hashing.
    """
    sha256 = hashlib.sha256()
    file_stream.seek(0)
    while chunk := file_stream.read(8192):
        sha256.update(chunk)
    file_stream.seek(0)
    return sha256.hexdigest()


def process_and_store_image(file_stream: object, original_filename: str) -> Image:
    """Process an uploaded image and persist it to the active storage backend.

    Steps performed:
    1. Detach bytes from the Flask/Werkzeug stream.
    2. Compute a SHA-256 hash for deduplication.
    3. Gather metadata (MIME type, dimensions, format).
    4. Save the original file via the ``StorageProvider``.
    5. Create ``File`` and ``Image`` database records.
    6. Generate thumbnails for raster images.

    Returns the ``Image`` ORM instance (already flushed but not committed).
    """
    # Detach file data from Flask/Werkzeug early to prevent stream conflicts
    file_bytes: bytes = file_stream.read()

    # 1. Compute hash for deduplication
    file_hash = compute_file_hash(BytesIO(file_bytes))

    # 2. Return existing image if this exact file was already uploaded
    existing_file = File.query.filter_by(file_hash=file_hash).first()
    if existing_file:
        existing_image = Image.query.filter_by(file_id=existing_file.id).first()
        if existing_image:
            return existing_image

    # 3. Gather metadata
    mime_type, _ = mimetypes.guess_type(original_filename)
    mime_type = mime_type or 'application/octet-stream'

    ext = os.path.splitext(original_filename)[1].lower()
    if not ext and mime_type == 'image/jpeg':
        ext = '.jpg'

    storage_backend: str = current_app.config.get('STORAGE_DEFAULT_BACKEND', 'local')
    unique_id = uuid.uuid4().hex
    raw_key = f"{current_app.config.get('IMAGE_IMG_PATH')}/{unique_id}{ext}"
    storage_key = re.sub(r'/+', '/', raw_key.replace('\\', '/')).lstrip('/')

    # 4. Read image properties with PIL
    is_vector = mime_type == 'image/svg+xml'
    width: int = 0
    height: int = 0
    img_format: str = ''
    mode: str = ''

    if is_vector:
        img_format = 'SVG'
        mode = 'RGB'
    else:
        try:
            with ImagePIL.open(BytesIO(file_bytes)) as pil_img:
                width, height = pil_img.size
                img_format = pil_img.format
                mode = pil_img.mode
        except Exception as e:
            current_app.logger.error(f"Failed to read image {original_filename}: {e}")
            raise ValueError("Invalid image file")

    # 5. Persist the original file to storage
    file_obj = File(
        original_filename=original_filename,
        storage_backend=storage_backend,
        storage_key=storage_key,
        mime_type=mime_type,
        file_size=len(file_bytes),
        file_hash=file_hash,
        hash_algorithm='sha256',
    )

    provider = file_obj.get_provider()
    provider.save(storage_key, BytesIO(file_bytes), mime_type)

    db.session.add(file_obj)
    db.session.flush()

    # 6. Create the Image record
    image_obj = Image(
        file_obj=file_obj,
        is_vector=is_vector,
        width=width,
        height=height,
        format=img_format,
        mode=mode,
    )
    db.session.add(image_obj)
    db.session.flush()

    # 7. Generate thumbnails (raster images only)
    if not is_vector:
        _generate_thumbnails(
            file_bytes, image_obj, provider,
            storage_backend, unique_id, original_filename,
            width, height,
        )

    return image_obj


def _generate_thumbnails(
    file_bytes: bytes,
    image_obj: Image,
    provider: object,
    storage_backend: str,
    unique_id: str,
    original_filename: str,
    width: int,
    height: int,
) -> None:
    """Create and store resized thumbnail versions of the original image."""
    sizes: list[int] = current_app.config.get('THUMBNAIL_SIZES')
    thumb_format: str = current_app.config.get('IMAGE_DEFAULT_FORMAT', 'JPEG')
    max_dim = max(width, height)

    with ImagePIL.open(BytesIO(file_bytes)) as pil_img:
        if pil_img.mode == 'RGBA':
            background = ImagePIL.new('RGB', pil_img.size, (255, 255, 255))
            background.paste(pil_img, mask=pil_img.split()[3])
            pil_img = background

        for size in sizes:
            if size >= max_dim:
                continue

            thumb_img = pil_img.copy()
            thumb_img.thumbnail((size, size))

            thumb_stream = BytesIO()
            thumb_img.save(thumb_stream, format=thumb_format)
            thumb_stream.seek(0)

            raw_thumb_key = f"{current_app.config.get('IMAGE_TIMG_PATH')}/{unique_id}_{size}.{thumb_format.lower()}"
            thumb_key = re.sub(r'/+', '/', raw_thumb_key.replace('\\', '/')).lstrip('/')
            thumb_mime = f"image/{thumb_format.lower()}"

            thumb_file = File(
                original_filename=f"thumb_{size}_{original_filename}",
                storage_backend=storage_backend,
                storage_key=thumb_key,
                mime_type=thumb_mime,
                file_size=len(thumb_stream.getvalue()),
                file_hash=compute_file_hash(thumb_stream),
                hash_algorithm='sha256',
            )

            thumb_stream.seek(0)
            provider.save(thumb_key, thumb_stream, thumb_mime)

            db.session.add(thumb_file)
            db.session.flush()

            thumbnail_obj = Thumbnail(
                image=image_obj,
                size=size,
                file_obj=thumb_file,
            )
            thumbnail_obj.format = thumb_format
            thumbnail_obj.mode = thumb_img.mode
            db.session.add(thumbnail_obj)
