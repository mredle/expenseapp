# -*- coding: utf-8 -*-

import os
import re
import shutil
from flask import current_app

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None

class StorageProvider:
    """Base interface for storage providers."""
    def save(self, storage_key, file_stream, mime_type=None):
        raise NotImplementedError

    def delete(self, storage_key):
        raise NotImplementedError

    def get_url(self, storage_key):
        raise NotImplementedError
        
    def get_local_path(self, storage_key):
        """Returns a local file path if available (useful for PIL processing)."""
        raise NotImplementedError
    
    def get_file_stream(self, storage_key):
        """Returns a readable byte stream of the file."""
        raise NotImplementedError

class LocalStorageProvider(StorageProvider):
    """Stores files on the local filesystem."""
    def __init__(self, base_path, base_url):
        self.base_path = base_path
        self.base_url = base_url

    def _get_full_path(self, storage_key):
        return os.path.join(self.base_path, storage_key)

    def save(self, storage_key, file_stream, mime_type=None):
        full_path = self._get_full_path(storage_key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # If the stream is already a file path, we can copy it directly
        if isinstance(file_stream, str) and os.path.exists(file_stream):
            shutil.copy(file_stream, full_path)
        else:
            with open(full_path, 'wb') as f:
                shutil.copyfileobj(file_stream, f)

    def delete(self, storage_key):
        full_path = self._get_full_path(storage_key)
        if os.path.exists(full_path):
            os.remove(full_path)

    def get_url(self, storage_key):
        # Maps the storage key to your local static serving route
        return os.path.join(self.base_url, storage_key).replace('\\', '/').replace('//', '/')
        
    def get_local_path(self, storage_key):
        return self._get_full_path(storage_key)

    def get_file_stream(self, storage_key):
        full_path = self._get_full_path(storage_key)
        # Return a standard Python file object
        return open(full_path, 'rb')

class S3StorageProvider(StorageProvider):
    """Stores files in an S3-compatible object store."""
    def __init__(self, bucket_name, region_name, endpoint_url=None):
        if boto3 is None:
            raise ImportError("The 'boto3' library is required for S3 storage. Run 'pip install boto3'.")
            
        self.bucket_name = bucket_name
        self.s3 = boto3.client(
            's3', 
            region_name=region_name, 
            endpoint_url=endpoint_url
        )

    def _sanitize_key(self, storage_key):
        """Ensures keys are MinIO/S3 compliant by stripping bad slashes."""
        if not storage_key:
            return storage_key
        # 1. Convert Windows backslashes to forward slashes
        clean_key = storage_key.replace('\\', '/')
        # 2. Remove multiple consecutive slashes (e.g., img//file.jpg -> img/file.jpg)
        clean_key = re.sub(r'/+', '/', clean_key)
        # 3. Remove leading slashes
        return clean_key.lstrip('/')

    def save(self, storage_key, file_stream, mime_type=None):
        storage_key = self._sanitize_key(storage_key) # Clean before saving
        ExtraArgs = {'ContentType': mime_type} if mime_type else {}
        
        if isinstance(file_stream, str) and os.path.exists(file_stream):
            with open(file_stream, 'rb') as data:
                self.s3.upload_fileobj(data, self.bucket_name, storage_key, ExtraArgs=ExtraArgs)
        else:
            self.s3.upload_fileobj(file_stream, self.bucket_name, storage_key, ExtraArgs=ExtraArgs)

    def delete(self, storage_key):
        storage_key = self._sanitize_key(storage_key) # Clean before deleting
        self.s3.delete_object(Bucket=self.bucket_name, Key=storage_key)

    def get_url(self, storage_key):
        # Generate the public URL for the S3 object
        storage_key = self._sanitize_key(storage_key) # Clean before linking
        endpoint = self.s3.meta.endpoint_url
        return f"{endpoint}/{self.bucket_name}/{storage_key}"
        
    def get_local_path(self, storage_key):
        """S3 doesn't have local paths. If PIL needs to process it, it must be downloaded first."""
        return None

    def get_file_stream(self, storage_key):
        # s3.get_object returns a dictionary where 'Body' is a botocore StreamingBody
        storage_key = self._sanitize_key(storage_key) # Clean before fetching
        response = self.s3.get_object(Bucket=self.bucket_name, Key=storage_key)
        return response['Body']

def get_storage_provider(backend_name):
    """Factory function to instantiate the correct provider."""
    if backend_name == 'local':
        return LocalStorageProvider(
            base_path=current_app.config.get('STORAGE_LOCAL_PATH', current_app.config['IMAGE_ROOT_PATH']),
            base_url='/' # Your base route for media
        )
    elif backend_name == 's3':
        return S3StorageProvider(
            bucket_name=current_app.config['S3_BUCKET_NAME'],
            region_name=current_app.config.get('S3_REGION'),
            endpoint_url=current_app.config.get('S3_ENDPOINT_URL')
        )
    else:
        raise ValueError(f"Unknown storage backend: {backend_name}")
