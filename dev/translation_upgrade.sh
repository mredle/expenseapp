#!/bin/bash
cd ..
source activate flask_app
export FLASK_APP=./expenseapp.py
flask translate update
