# Use an official Python runtime as a parent image
FROM continuumio/miniconda3
SHELL ["/bin/bash", "-c"]

# Setup python environment with conda
COPY environment_flask_app.yml /tmp/environment.yml
RUN conda env update -n root --file /tmp/environment.yml \
    && conda clean --all

# Install app
RUN adduser --gecos "" --disabled-password flask_app
WORKDIR /home/flask_app
USER flask_app
COPY --chown=flask_app:flask_app app app
COPY --chown=flask_app:flask_app migrations migrations
COPY --chown=flask_app:flask_app expenseapp.py config.py boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP expenseapp.py
EXPOSE 5000
VOLUME ["/home/flask_app/static"]
ENTRYPOINT ["./boot.sh"]
