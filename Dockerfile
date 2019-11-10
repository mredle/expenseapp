# Use an official Python runtime as a parent image
FROM python:3.7-alpine
SHELL ["/bin/sh", "-c"]

# Setup python environment with pip
RUN apk --update --upgrade --no-cache add \
    cairo-dev pango-dev gdk-pixbuf font-noto
    
COPY requirements.txt /tmp/requirements.txt
RUN apk add --no-cache --virtual .build-deps build-base linux-headers && \
    apk add --no-cache freetype-dev \
                       gcc \
                       jpeg-dev \
                       lcms2-dev \
                       libffi-dev \
                       openjpeg-dev \
                       musl-dev \
                       tcl-dev \
                       tiff-dev \
                       tk-dev \
                       zlib-dev && \
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
RUN chmod +x entrypoint.sh

ENV FLASK_APP expenseapp.py
EXPOSE 5000
VOLUME ["/home/flask_app/app/static"]
ENTRYPOINT ["sh", "./entrypoint.sh"]
