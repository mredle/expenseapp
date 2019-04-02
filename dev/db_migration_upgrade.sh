#!/bin/bash
cd ..
source activate flask_app
export FLASK_APP=./expenseapp.py
flask db migrate
flask db upgrade
