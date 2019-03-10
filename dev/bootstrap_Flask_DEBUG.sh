#!/bin/bash
cd ..
source activate flask_app_dev
export FLASK_APP=./expenseapp.py
export FLASK_DEBUG=1
mkdir -p app/static/img
mkdir -p app/static/timg
mkdir -p app/static/tmp

flask db upgrade
flask dbinit currency
flask dbinit admin
flask dbinit dummyusers --count 3
flask translate compile
flask run -h localhost
