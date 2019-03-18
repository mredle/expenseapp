# Use an official Python runtime as a parent image
FROM python:3.7-alpine
SHELL ["/bin/sh", "-c"]

# Setup python environment with pip
COPY requirements.txt /tmp/requirements.txt
RUN apk add --no-cache jpeg-dev zlib-dev && \
    apk add --no-cache --virtual .build-deps build-base linux-headers && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --ignore-installed -r /tmp/requirements.txt && \
    apk del .build-deps

# Install app
ARG DUMMY=unknown
RUN DUMMY=${DUMMY} adduser --gecos "" --disabled-password flask_app
WORKDIR /home/flask_app
USER flask_app
COPY --chown=flask_app:flask_app app app
COPY --chown=flask_app:flask_app migrations migrations
COPY --chown=flask_app:flask_app expenseapp.py config.py entrypoint.sh ./
RUN chmod +x entrypoint.sh && \
    mkdir -p app/static/img && \
    mkdir -p app/static/timg && \
    mkdir -p app/static/tmp

ENV FLASK_APP expenseapp.py
EXPOSE 5000
VOLUME ["/home/flask_app/app/static"]
ENTRYPOINT ["sh", "./entrypoint.sh"]
