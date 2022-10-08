#!/bin/bash
cd ../..
source venv/bin/activate
export FLASK_APP=./expenseapp.py
flask db migrate
flask db upgrade
