#!/bin/bash

docker-compose -f scripts/dev/docker-compose.yml  up -d
source create_venv_pyenv.sh

export FLASK_APP=./expenseapp.py
export FLASK_DEBUG=1
export DB_TYPE=mysql
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=user
export DB_PW=pw
export DB_NAME=expenseapp

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
