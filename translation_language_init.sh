#!/bin/bash
export FLASK_APP=./expenseapp.py
source activate flask_app
flask translate init $1
