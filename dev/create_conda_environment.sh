#!/bin/bash
ENVNAME=flask_app

# create environment
conda create -n $ENVNAME python=3.7
source activate $ENVNAME

# add pip packages for prod environment
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir --ignore-installed -r ../requirements.txt

# add pip packages for dev environment
pip install --no-cache-dir --ignore-installed -r ./requirements.txt
