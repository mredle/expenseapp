#!/bin/bash

ENVNAME=flask_app

# create environment
conda create -n $ENVNAME python=3.6
source activate $ENVNAME
conda config --append channels conda-forge

# add conda packages
conda install  -n $ENVNAME Pillow ipython redis-py=2.10.6 rq python-dotenv pyjwt gunicorn pymysql flask flask-sqlalchemy flask-migrate flask-login flask-mail flask-moment flask-babel flask-httpauth flask-wtf

# add pip packages
pip install flask-bootstrap flask-shell-ipython flask-uploads

# export conda environment file
conda env export > environment.yml
pip freeze > requirements.txt
