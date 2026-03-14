#!/bin/bash


source create_venv_pyenv.sh

export FLASK_APP="./expenseapp.py"
export FLASK_DEBUG=1
export DB_TYPE="oci"
export DB_HOST="adb.eu-zurich-1.oraclecloud.com"
export DB_PORT=1522
export DB_USER="user"
export DB_PW="ps"
export DB_NAME="adb_tp"
export TNS_ADMIN="/opt/Wallet/"
export WALLET_PW="pw"
export STORAGE_DEFAULT_BACKEND="s3"
export S3_BUCKET_NAME="expenseapp-bucket"
export S3_REGION="eu-central-1"
export AWS_ACCESS_KEY_ID="s3user"
export AWS_SECRET_ACCESS_KEY="s3pw"
export S3_ENDPOINT_URL="http://localhost:9000"

while true; do
    sleep 10
    flask db upgrade
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo "Upgrade command failed, retrying in 10 secs..."
done

flask db upgrade
flask dbinit admin --overwrite
flask dbinit icons --overwrite --subfolder icons
flask dbinit currencies --overwrite
flask dbinit dummyusers --count 3
flask dbmaint add-missing-guid
flask translate compile

#echo "Performing development factory reset..."
#flask flush-s3
#flask flush-db
#flask flush-media-cache

echo "Starting Flask development server..."
flask run --host=0.0.0.0
