FROM python:3

WORKDIR /app

#COPY requirements.txt ./
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
RUN python manage.py collectstatic --noinput


CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000" ]
