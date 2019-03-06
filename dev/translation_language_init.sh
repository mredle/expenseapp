#!/bin/bash
cd ..
source activate flask_app_dev
export FLASK_APP=./expenseapp.py
flask translate init $1
