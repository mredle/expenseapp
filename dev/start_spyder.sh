#!/bin/bash
cd ..
source activate flask_app
export FLASK_APP=./expenseapp.py
export FLASK_DEBUG=1
spyder -w .&
