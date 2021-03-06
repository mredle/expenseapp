#!/bin/bash
ENVNAME=flask_app

# create environment
conda create -n $ENVNAME -y python=3.8
conda install -n $ENVNAME -y ipython spyder
source activate $ENVNAME
pip install --no-cache-dir --upgrade pip

# add pip packages for prod environment
pip install --no-cache-dir --ignore-installed -r ../requirements.txt

# add pip packages for dev environment
pip install --no-cache-dir flask-shell-ipython
