#!/bin/bash

sudo docker-compose up -d

cd ..
eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"
conda activate flask_app

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
flask dbmaint add-missing-guid
flask dbmaint clean-log --no-error --keepdays 30
flask translate compile
flask run -h localhost
