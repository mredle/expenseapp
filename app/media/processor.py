# coding=utf-8

import os
import re
import uuid
import hashlib
import mimetypes
from io import BytesIO
from PIL import Image as ImagePIL
from flask import current_app
from app import db
from app.models import File, Image, Thumbnail

def compute_file_hash(file_stream):
    """Computes the SHA256 hash of a file stream."""
    sha256 = hashlib.sha256()
    file_stream.seek(0)
    # Read in 8KB chunks to prevent memory spikes on large files
    while chunk := file_stream.read(8192):
        sha256.update(chunk)
    file_stream.seek(0)
    return sha256.hexdigest()

def process_and_store_image(file_stream, original_filename):
    """
    Processes an uploaded image stream, saves it to the active storage 
    backend, generates thumbnails, and returns the Image DB object.
    """
    # --- FIX: Detach the file data from Flask/Werkzeug early! ---
    # Reading the raw bytes once prevents third-party libraries (like 
    # PIL or boto3) from accidentally closing the shared stream on us.
    file_bytes = file_stream.read()
    # ------------------------------------------------------------
    
    # 1. Compute Hash for Deduplication (using a fresh memory stream)
    file_hash = compute_file_hash(BytesIO(file_bytes))
    
    # 2. Check if this exact file is already in our system
    existing_file = File.query.filter_by(file_hash=file_hash).first()
    if existing_file:
        existing_image = Image.query.filter_by(file_id=existing_file.id).first()
        if existing_image:
            return existing_image 

    # 3. Gather Metadata
    mime_type, _ = mimetypes.guess_type(original_filename)
    mime_type = mime_type or 'application/octet-stream'
    
    ext = os.path.splitext(original_filename)[1].lower()
    if not ext and mime_type == 'image/jpeg': 
        ext = '.jpg'
    
    # Generate Storage Key securely (with sanitization!)
    storage_backend = current_app.config.get('STORAGE_DEFAULT_BACKEND', 'local')
    unique_id = uuid.uuid4().hex
    raw_key = f"{current_app.config.get('IMAGE_IMG_PATH')}/{unique_id}{ext}" # Or however you map your folders
    storage_key = re.sub(r'/+', '/', raw_key.replace('\\', '/')).lstrip('/')
    
    # 4. Process Image properties using PIL
    vector = (mime_type == 'image/svg+xml')
    width, height = 0, 0
    img_format, mode = '', ''
    
    if vector:
        img_format = 'SVG'
        mode = 'RGB'
    else:
        try:
            # Give PIL its own isolated memory stream!
            with ImagePIL.open(BytesIO(file_bytes)) as pil_img:
                width, height = pil_img.size
                img_format = pil_img.format
                mode = pil_img.mode
        except Exception as e:
            current_app.logger.error(f"Failed to read image {original_filename}: {e}")
            raise ValueError("Invalid image file")
    
    # 5. Save the Original File to Storage
    file_obj = File(
        original_filename=original_filename,
        storage_backend=storage_backend,
        storage_key=storage_key,
        mime_type=mime_type,
        file_hash=file_hash,
        hash_algorithm='sha256'
    )
    
    provider = file_obj.get_provider()
    
    # Give boto3 its own isolated memory stream!
    provider.save(storage_key, BytesIO(file_bytes), mime_type)
    
    db.session.add(file_obj)
    db.session.flush() 
    
    # 6. Create the Image Record
    image_obj = Image(
        file_obj=file_obj,
        vector=vector,
        width=width,
        height=height,
        format=img_format,
        mode=mode
    )
    db.session.add(image_obj)
    db.session.flush()
    
    # 7. Generate Thumbnails (if not vector)
    if not vector:
        sizes = current_app.config.get('THUMBNAIL_SIZES')
        
        # Give PIL one last isolated memory stream!
        with ImagePIL.open(BytesIO(file_bytes)) as pil_img:
            if pil_img.mode == 'RGBA':
                background = ImagePIL.new('RGB', pil_img.size, (255, 255, 255))
                background.paste(pil_img, mask=pil_img.split()[3])
                pil_img = background
            
            max_dim = max(width, height)
            thumb_format = current_app.config.get('IMAGE_DEFAULT_FORMAT', 'JPEG')
            
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
                    file_hash=compute_file_hash(thumb_stream),
                    hash_algorithm='sha256'
                )
                
                thumb_stream.seek(0)
                provider.save(thumb_key, thumb_stream, thumb_mime)
                
                db.session.add(thumb_file)
                db.session.flush()
                
                thumbnail_obj = Thumbnail(
                    image=image_obj,
                    size=size,
                    file_obj=thumb_file
                )
                thumbnail_obj.format = thumb_format
                thumbnail_obj.mode = thumb_img.mode
                db.session.add(thumbnail_obj)
                
    return image_obj