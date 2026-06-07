#!/bin/bash

source create_venv_pyenv_dev.sh

export FLASK_APP="./expenseapp.py"
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

echo "Starting RQ worker for 'expenseapp-tasks'..."
exec rq worker -u "redis://:pw@localhost:6379/0" expenseapp-tasks
