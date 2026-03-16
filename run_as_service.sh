#!/bin/bash

# Activate the pre-built virtual environment
source /opt/expenseapp/venv/bin/activate

export FLASK_APP=./expenseapp.py

while true; do
    sleep 10
    flask db upgrade
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo Upgrade command failed, retrying in 10 secs...
done

flask dbinit admin --overwrite
flask dbinit icons --no-overwrite --subfolder icons
flask dbinit currencies --overwrite
flask dbinit currency-flags --overwrite
flask dbmaint add-missing-guid
flask translate compile
exec gunicorn -b :5000 --access-logfile - --error-logfile - expenseapp:app
