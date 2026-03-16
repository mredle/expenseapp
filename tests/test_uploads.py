# -*- coding: utf-8 -*-
from PIL import Image
from io import BytesIO

def test_upload_profile_picture(auth_client):
    """Test that uploading a profile picture processes and saves the file."""
    
    # 1. Create a REAL valid image file entirely in memory!
    img = Image.new('RGB', (100, 100), color='red')
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    
    dummy_file = (img_io, 'test_image.jpg')
    
    # 2. POST the file to the endpoint
    response = auth_client.post('/edit_profile_picture', data={
        'image': dummy_file
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Your changes have been saved." in response.data