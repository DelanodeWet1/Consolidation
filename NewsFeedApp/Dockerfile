FROM python:3.12-slim-bookworm

# Don't write .pyc files, and don't buffer output so logs appear immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# mysqlclient is compiled from source, so it needs a compiler and the
# MariaDB/MySQL client headers.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so Docker can cache this layer: it only
# re-runs when requirements.txt changes, not on every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# 0.0.0.0 (not 127.0.0.1) so the server is reachable from outside the
# container. runserver is Django's development server - fine for coursework
# and demos, but not what you'd use in production.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
