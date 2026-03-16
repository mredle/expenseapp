#!/bin/bash

docker-compose -f scripts/dev/docker-compose.yml  up -d
source create_venv_pyenv_dev.sh

export FLASK_APP="./expenseapp.py"
export FLASK_DEBUG=1
export DB_TYPE="mysql"
export DB_HOST="localhost"
export DB_PORT=3306
export DB_USER="user"
export DB_PW="pw"
export DB_NAME="expenseapp"
export STORAGE_DEFAULT_BACKEND="s3"
export S3_BUCKET_NAME="expenseapp-bucket"
export S3_REGION="eu-central-1"
export AWS_ACCESS_KEY_ID="minioadmin"
export AWS_SECRET_ACCESS_KEY="minioadminpw"
export S3_ENDPOINT_URL="http://localhost:9000"

echo "Performing development factory reset..."
flask flush-s3
flask flush-db-force
flask flush-media-cache

echo "Initializing database..."
flask db upgrade
flask dbinit admin --overwrite
#flask dbinit icons --no-overwrite --subfolder icons
flask dbinit currencies --overwrite
flask dbinit dummyusers --count 3
flask dbmaint add-missing-guid

python -m pytest --cov=app tests/

echo "Starting Flask development server to inspect result..."
flask run --host=0.0.0.0