#!/bin/bash
ENVNAME=flask_app

# create environment
conda create -n $ENVNAME -y python=3.10
conda install -n $ENVNAME -y ipython spyder

eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"
conda activate $ENVNAME

pip install --no-cache-dir --upgrade pip

# add pip packages for prod environment
pip install --no-cache-dir --ignore-installed -r ../requirements.txt

# add pip packages for dev environment
pip install --no-cache-dir flask-shell-ipython
