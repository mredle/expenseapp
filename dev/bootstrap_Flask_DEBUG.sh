#!/bin/bash
docker-compose up -d

cd ..
source activate flask_app
export FLASK_APP=./expenseapp.py
export FLASK_DEBUG=1
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=user
export MYSQL_PW=pw
export MYSQL_DB=expenseapp

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
flask dbinit add-missing-guid
flask translate compile
flask run -h localhost
