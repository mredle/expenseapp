# Use an official Python runtime as a parent image
FROM continuumio/miniconda3
SHELL ["/bin/bash", "-c"]

# Setup python environment with conda
COPY prod/environment_flask_app.yml /tmp/environment.yml
RUN conda env update -n root --file /tmp/environment.yml \
    && conda clean --all

# Install app
ARG DUMMY=unknown
RUN DUMMY=${DUMMY} adduser --gecos "" --disabled-password flask_app
WORKDIR /home/flask_app
USER flask_app
COPY --chown=flask_app:flask_app app app
COPY --chown=flask_app:flask_app migrations migrations
COPY --chown=flask_app:flask_app expenseapp.py config.py entrypoint.sh ./
RUN chmod +x entrypoint.sh \
    && mkdir -p app/static/img \
    && mkdir -p app/static/timg \
    && mkdir -p app/static/tmp

ENV FLASK_APP expenseapp.py
EXPOSE 5000
VOLUME ["/home/flask_app/app/static"]
ENTRYPOINT ["./entrypoint.sh"]
