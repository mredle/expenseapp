#!/bin/sh

# Enable CodeReady Builder (CRB) — required for several -devel packages
# (lcms2-devel, openjpeg2-devel, libtiff-devel, etc.) that live outside BaseOS/AppStream.
dnf install -y dnf-utils
dnf config-manager --set-enabled ol10_codeready_builder

# System build/runtime dependencies (WeasyPrint, Pillow, etc.)
dnf install -y \
    gcc \
    pango \
    gdk-pixbuf2 \
    google-noto-sans-fonts \
    freetype-devel \
    libjpeg-turbo-devel \
    lcms2-devel \
    libffi-devel \
    openjpeg2-devel \
    tcl-devel \
    libtiff-devel \
    tk-devel \
    zlib-devel \
    curl \
    ca-certificates

# Node.js 22.x + npm for the Ionic/Angular mobile build.
# The AppStream nodejs module may lag behind; use NodeSource for a guaranteed 22.x
# (requires Node >= 20.19/22.12 for Angular 20).
curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -
dnf install -y nodejs
