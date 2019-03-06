#!/bin/bash

ENVNAME=flask_app_dev

# create environment
conda create -n $ENVNAME python=3.6
source activate $ENVNAME
conda config --append channels conda-forge

# add conda packages
conda install  -n $ENVNAME Pillow spyder ipython rq python-dotenv pyjwt gunicorn pymysql flask flask-sqlalchemy flask-migrate flask-login flask-mail flask-moment flask-babel flask-httpauth flask-wtf

# add pip packages
pip install flask-bootstrap flask-shell-ipython flask-uploads

# export conda environment file
conda env export > environment_$ENVNAME.yml
