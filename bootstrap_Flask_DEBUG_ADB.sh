#!/bin/bash

source create_venv_pyenv.sh

export FLASK_APP=./expenseapp.py
export FLASK_DEBUG=1
export DB_TYPE=oci
export DB_HOST=adb.eu-zurich-1.oraclecloud.com
export DB_PORT=1522
export DB_USER=expenseapp
export DB_PW=pw
export DB_NAME=testadb_tp
export TNS_ADMIN=/tmp/Wallet
export WALLET_PW=pw

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
flask run -h 0.0.0.0
