#!/bin/sh

# System build/runtime dependencies (WeasyPrint, Pillow, etc.)
apt install gcc \
            libpangocairo-1.0-0 \
            libgdk-pixbuf2.0-0 \
            fonts-noto \
            libfreetype6-dev \
            libjpeg-dev \
            liblcms2-dev \
            libffi-dev \
            libopenjp2-7-dev \
            musl-dev \
            tcl-dev \
            libtiff-dev \
            tk-dev \
            zlib1g-dev \
            curl \
            ca-certificates \
            git \
            wget

# pyenv build dependencies — required to compile CPython 3.14.x from source.
# See: https://github.com/pyenv/pyenv/wiki#suggested-build-environment
apt install make \
            build-essential \
            libssl-dev \
            libbz2-dev \
            libreadline-dev \
            libsqlite3-dev \
            llvm \
            libncursesw5-dev \
            xz-utils \
            libxml2-dev \
            libxmlsec1-dev \
            liblzma-dev

# Node.js 22.x + npm for the Ionic/Angular mobile build.
# The distro 'nodejs' package is too old for Angular 20 (requires Node >= 20.19/22.12),
# so install from NodeSource which bundles a compatible npm.
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install nodejs