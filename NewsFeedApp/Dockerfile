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

# Collect static files. manage.py imports settings.py, which requires
# DJANGO_SECRET_KEY and DB_PASSWORD - but .env isn't available at build time
# (it's dockerignored, and compose's env_file only applies when the container
# runs). The placeholders below exist only for this one command: they aren't
# stored in the image's environment and aren't used for anything real.
RUN DJANGO_SECRET_KEY=build-only-placeholder DB_PASSWORD=build-only-placeholder \
    python manage.py collectstatic --noinput

EXPOSE 8000

# 0.0.0.0 (not 127.0.0.1) so the server is reachable from outside the
# container. runserver is Django's development server - fine for coursework
# and demos, but not what you'd use in production.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]