"""Unified storage abstraction supporting local filesystem and S3-compatible backends."""

from __future__ import annotations

import os
import re
import shutil
from typing import IO, TYPE_CHECKING

from flask import current_app

if TYPE_CHECKING:
    from botocore.response import StreamingBody
    from mypy_boto3_s3 import S3Client

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError  # noqa: F401
except ImportError:
    boto3 = None  # type: ignore[assignment]


class StorageProvider:
    """Base interface for storage providers.

    Subclasses must implement all methods.  Raising ``NotImplementedError``
    ensures a clear failure when a required operation is missing.
    """

    def save(self, storage_key: str, file_stream: str | IO[bytes], mime_type: str | None = None) -> None:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError

    def get_url(self, storage_key: str) -> str:
        raise NotImplementedError

    def get_local_path(self, storage_key: str) -> str | None:
        """Return a local file path if available (useful for PIL processing)."""
        raise NotImplementedError

    def get_file_stream(self, storage_key: str) -> IO[bytes]:
        """Return a readable byte stream of the file."""
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    """Store files on the local filesystem."""

    def __init__(self, base_path: str, base_url: str) -> None:
        self.base_path = base_path
        self.base_url = base_url

    def _get_full_path(self, storage_key: str) -> str:
        """Resolve *storage_key* to an absolute filesystem path."""
        return os.path.join(self.base_path, storage_key)

    def save(self, storage_key: str, file_stream: str | IO[bytes], mime_type: str | None = None) -> None:
        """Persist *file_stream* (path or file object) under *storage_key*."""
        full_path = self._get_full_path(storage_key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # If the stream is already a file path, copy it directly.
        if isinstance(file_stream, str) and os.path.exists(file_stream):
            shutil.copy(file_stream, full_path)
        else:
            with open(full_path, 'wb') as f:
                shutil.copyfileobj(file_stream, f)  # type: ignore[arg-type]

    def delete(self, storage_key: str) -> None:
        """Remove the file identified by *storage_key*, if it exists."""
        full_path = self._get_full_path(storage_key)
        if os.path.exists(full_path):
            os.remove(full_path)

    def get_url(self, storage_key: str) -> str:
        """Return a URL path suitable for serving via the local web server."""
        return os.path.join(self.base_url, storage_key).replace('\\', '/').replace('//', '/')

    def get_local_path(self, storage_key: str) -> str:
        """Return the absolute local filesystem path."""
        return self._get_full_path(storage_key)

    def get_file_stream(self, storage_key: str) -> IO[bytes]:
        """Return an open binary file handle for *storage_key*."""
        full_path = self._get_full_path(storage_key)
        return open(full_path, 'rb')


class S3StorageProvider(StorageProvider):
    """Store files in an S3-compatible object store."""

    def __init__(self, bucket_name: str, region_name: str | None, endpoint_url: str | None = None) -> None:
        if boto3 is None:
            raise ImportError(
                "The 'boto3' library is required for S3 storage. "
                "Run 'pip install boto3'."
            )

        self.bucket_name = bucket_name

        # Bypass the boto3 >=1.36.0 checksum bug for OCI-compatible endpoints.
        oci_compat_config = Config(
            request_checksum_calculation='WHEN_REQUIRED',
            response_checksum_validation='WHEN_REQUIRED',
        )

        self.s3: S3Client = boto3.client(
            's3',
            region_name=region_name,
            endpoint_url=endpoint_url,
            config=oci_compat_config,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_key(storage_key: str) -> str:
        """Ensure keys are S3/MinIO compliant by normalising slashes."""
        if not storage_key:
            return storage_key
        # Convert Windows backslashes → forward slashes
        clean_key = storage_key.replace('\\', '/')
        # Collapse consecutive slashes (e.g. img//file.jpg → img/file.jpg)
        clean_key = re.sub(r'/+', '/', clean_key)
        # Strip leading slash
        return clean_key.lstrip('/')

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, storage_key: str, file_stream: str | IO[bytes], mime_type: str | None = None) -> None:
        """Upload *file_stream* to the bucket under *storage_key*."""
        storage_key = self._sanitize_key(storage_key)
        extra_args: dict[str, str] = {'ContentType': mime_type} if mime_type else {}

        if isinstance(file_stream, str) and os.path.exists(file_stream):
            with open(file_stream, 'rb') as data:
                self.s3.upload_fileobj(data, self.bucket_name, storage_key, ExtraArgs=extra_args)
        else:
            self.s3.upload_fileobj(file_stream, self.bucket_name, storage_key, ExtraArgs=extra_args)  # type: ignore[arg-type]

    def delete(self, storage_key: str) -> None:
        """Delete the object identified by *storage_key* from the bucket."""
        storage_key = self._sanitize_key(storage_key)
        self.s3.delete_object(Bucket=self.bucket_name, Key=storage_key)

    def get_url(self, storage_key: str) -> str:
        """Return the public URL for the S3 object."""
        storage_key = self._sanitize_key(storage_key)
        endpoint = self.s3.meta.endpoint_url
        return f"{endpoint}/{self.bucket_name}/{storage_key}"

    def get_local_path(self, storage_key: str) -> None:
        """S3 has no local paths; return ``None``.

        If PIL processing is required the caller must download the object
        first.
        """
        return None

    def get_file_stream(self, storage_key: str) -> StreamingBody:
        """Return a streaming body for the S3 object."""
        storage_key = self._sanitize_key(storage_key)
        response = self.s3.get_object(Bucket=self.bucket_name, Key=storage_key)
        return response['Body']


def get_storage_provider(backend_name: str) -> StorageProvider:
    """Factory: instantiate the correct provider based on *backend_name*.

    Supported values: ``'local'``, ``'s3'``.
    """
    if backend_name == 'local':
        return LocalStorageProvider(
            base_path=current_app.config.get('STORAGE_LOCAL_PATH', current_app.config['IMAGE_ROOT_PATH']),
            base_url='/',
        )
    if backend_name == 's3':
        return S3StorageProvider(
            bucket_name=current_app.config['S3_BUCKET_NAME'],
            region_name=current_app.config.get('S3_REGION'),
            endpoint_url=current_app.config.get('S3_ENDPOINT_URL'),
        )
    raise ValueError(f"Unknown storage backend: {backend_name}")
