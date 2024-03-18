FROM python:3-alpine

WORKDIR /app

COPY requirements.txt .
COPY static static
COPY templates templates
COPY *.py .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
CMD ["python", "main.py"]
