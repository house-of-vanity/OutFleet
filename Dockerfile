FROM python:3-slim

WORKDIR /app

COPY ./requirements.txt .
RUN apk update && apk add git && pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput


CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000" ]
