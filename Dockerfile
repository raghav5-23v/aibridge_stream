FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["gunicorn", "--worker-class", "gevent", \
    "--workers", "2", \
    "--worker-connections", "1000", \
    "--bind", "0.0.0.0:5000", \
    "--timeout", "300", \
    "app:app"]