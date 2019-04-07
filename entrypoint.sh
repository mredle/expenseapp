#!/bin/sh
while true; do
    sleep 10
    flask db upgrade
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo Upgrade command failed, retrying in 10 secs...
done

flask dbinit admin --overwrite
flask dbinit icons --overwrite --subfolder icons
flask dbinit currencies --overwrite
flask dbinit currency-flags --overwrite
flask translate compile
exec gunicorn -b :5000 --access-logfile - --error-logfile - expenseapp:app
