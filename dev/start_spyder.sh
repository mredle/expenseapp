#!/bin/bash
cd ..
eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"
conda activate flask_app

export FLASK_APP=./expenseapp.py
export FLASK_DEBUG=1
spyder -w .&
