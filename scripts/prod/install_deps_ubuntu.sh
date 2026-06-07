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
            ca-certificates

# Node.js 22.x + npm for the Ionic/Angular mobile build.
# The distro 'nodejs' package is too old for Angular 20 (requires Node >= 20.19/22.12),
# so install from NodeSource which bundles a compatible npm.
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install nodejs