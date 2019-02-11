#!/bin/bash
export FLASK_APP=./expenseapp.py
export FLASK_DEBUG=1
source activate flask_app_dev

flask db upgrade
flask dbinit dummy --count 3
flask translate compile
flask run -h localhost
