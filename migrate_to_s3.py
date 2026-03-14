#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from expenseapp import app
from app import db
from app.models import File
from app.storage import get_storage_provider

def run_migration():
    with app.app_context():
        local_files = File.query.filter_by(storage_backend='local').all()
        print(f"Found {len(local_files)} local files to migrate...")
        
        if not local_files:
            return

        try:
            s3_provider = get_storage_provider('s3')
            local_provider = get_storage_provider('local')
        except Exception as e:
            print(f"Failed to initialize storage providers: {e}")
            return
            
        success = 0
        missing = 0
        errors = 0
        
        for f_obj in local_files:
            local_path = local_provider.get_local_path(f_obj.storage_key)
            
            # Skip if the physical file doesn't exist (e.g., the orphaned records we bypassed)
            if not os.path.isfile(local_path):
                print(f"[{f_obj.id}] Skipped (Missing local file): {local_path}")
                missing += 1
                continue
            
            # Remove double slashes that MinIO rejects
            clean_storage_key = f_obj.storage_key.replace('//', '/')
            
            # Also strip any leading slashes just in case
            if clean_storage_key.startswith('/'):
                clean_storage_key = clean_storage_key[1:]

            # Migrate from old to new storage prefixes
            clean_storage_key = clean_storage_key.replace('static/img', 'images')
            clean_storage_key = clean_storage_key.replace('static/timg', 'thumbnails')
            
            try:
                # 1. Read from local disk and upload to S3
                with open(local_path, 'rb') as file_data:
                    s3_provider.save(clean_storage_key, file_data, f_obj.mime_type)
                
                # 2. Update the database record to point to S3
                f_obj.storage_key = clean_storage_key
                f_obj.storage_backend = 's3'
                db.session.commit()
                
                # 3. Optional: Delete the local file to free up disk space!
                # os.remove(local_path)
                
                success += 1
                print(f"[{f_obj.id}] Migrated successfully: {clean_storage_key}")
                
            except Exception as e:
                print(f"[{f_obj.id}] Error migrating {clean_storage_key}: {e}")
                errors += 1
                db.session.rollback()
                
        print("\n=== Migration Complete ===")
        print(f"Successfully Migrated: {success}")
        print(f"Missing Local Files:   {missing}")
        print(f"Errors:                {errors}")

if __name__ == '__main__':
    run_migration()