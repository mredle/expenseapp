# expenseapp
Small app to manage expenses in a group

## prepare ubuntu host system
install python3.10
install dependencies
```bash
sudo apt install    python3-virtualenv \
                    python3-pip
```

clone repository and create virtual environment
```bash
git clone git@github.com:mredle/expenseapp.git
cd expenseapp
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## bootstrap app for debug
add pip packages for dev environment
```bash
pip install --no-cache-dir flask-shell-ipython
```

install dependencies
```bash
sudo apt    install libcairo-dev \
            libpango1.0-dev \
            libgdk-pixbuf2.0-0 \
            fonts-noto \
            libfreetype-dev \
            gcc \
            libjpeg-dev \
            liblcms2-dev \
            libffi-dev \
            libopenjp2-7-dev \
            musl-dev \
            tcl-dev \
            libtiff-dev \
            tk-dev \
            zlib1g-dev
```

start app
```bash
./bootstrap_Flask_DEBUG.sh
```