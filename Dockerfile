FROM rasa/rasa-sdk:3.1.2

WORKDIR /app

# COPY actions/requirements-actions.txt ./

USER root

# RUN pip install -r requirements-actions.txt

COPY ./actions /app/actions

USER 1001