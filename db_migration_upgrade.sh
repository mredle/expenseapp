#!/bin/bash
export FLASK_APP=./expenseapp.py
source activate flask_app
flask db migrate
flask db upgrade
