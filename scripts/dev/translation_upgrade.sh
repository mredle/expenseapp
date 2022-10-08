#!/bin/bash
cd ../..
source venv/bin/activate
export FLASK_APP=./expenseapp.py
flask translate update
