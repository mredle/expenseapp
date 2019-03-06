#!/bin/bash
export FLASK_APP=./expenseapp.py
source activate flask_app_dev
flask db init
