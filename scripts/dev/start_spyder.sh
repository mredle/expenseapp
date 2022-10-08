#!/bin/bash
cd ../..
source venv/bin/activate

export FLASK_APP=./expenseapp.py
export FLASK_DEBUG=1
spyder -w .&
