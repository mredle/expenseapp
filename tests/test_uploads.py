# coding=utf-8
"""Tests for file upload endpoints: profile picture processing and storage."""
from __future__ import annotations

from io import BytesIO

from flask.testing import FlaskClient
from PIL import Image


def test_upload_profile_picture(auth_client: FlaskClient) -> None:
    """Test that uploading a profile picture processes and saves the file."""
    img = Image.new('RGB', (100, 100), color='red')
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)

    dummy_file = (img_io, 'test_image.jpg')

    response = auth_client.post('/edit_profile_picture', data={
        'image': dummy_file
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Your changes have been saved." in response.data