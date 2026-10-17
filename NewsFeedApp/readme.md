# NewsFeedApp

A Django news platform with three account roles - **Reader**, **Journalist**, and **Editor** - split across two apps:

- **AuthApp** - registration, login, logout, and password reset
- **ArticlesAndMore** - articles, newsletters, publishers, journalist/reader subscriptions, and a small token-authenticated REST API

This guide assumes no prior Django experience. Follow the steps in order, copying and pasting the commands for your operating system.

You may find the project avialable for download at the following public repo: https://github.com/DelanodeWet1/NewsFeedApp

There are two ways to run the project:

- **With Docker** - nothing to install except Docker itself. See [Running with Docker](#running-with-docker).
- **Manually** - steps 1-10 below, which need Python and MySQL installed on your machine.

## Prerequisites

*These prerequisites are for the manual setup. If you're using Docker, skip to [Running with Docker](#running-with-docker).*

Before you start, make sure you have installed:

- **Python 3.11+** - check with `python3 --version` (macOS/Linux) or `python --version` (Windows)
- **pip** (comes with Python)
- **Git**
- **MySQL Server**, installed and running - this project stores its data in a MySQL database, not SQLite

If you don't have MySQL installed yet, install it for your OS before continuing:
- Windows/macOS: [MySQL Community Server](https://dev.mysql.com/downloads/mysql/)
- Linux (Debian/Ubuntu): `sudo apt install mysql-server`

## 1. Clone the project

```bash
git clone <your-repository-url>
```

## 2. Enter the project folder

```bash
cd NewsFeedApp
```

(If your cloned folder has a different name, `cd` into that instead - it's the folder containing `manage.py`.)

## 3. Create and activate a virtual environment

A virtual environment keeps this project's Python packages separate from the rest of your system.

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```bash
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```bash
python -m venv venv
venv\Scripts\Activate.ps1
```

You'll know it worked because your terminal prompt will now start with `(venv)`. Keep this terminal open (and the environment activated) for every step below.

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

This installs Django, Django REST Framework, `mysqlclient` (the MySQL driver), `python-dotenv` (loads your `.env` file - see step 6), and the project's other dependencies.

> **Having trouble installing `mysqlclient`?** This package needs MySQL's development headers to build. On Ubuntu/Debian: `sudo apt install python3-dev default-libmysqlclient-dev build-essential` and re-run the `pip install` command. On macOS with Homebrew: `brew install mysql-client pkg-config`.

## 5. Create the database

Log into MySQL:

```bash
mysql -u root -p
```

Enter your MySQL root password when prompted, then create the database:

```sql
CREATE DATABASE newsfeedapp_db;
EXIT;
```

## 6. Set up your environment variables

`settings.py` doesn't contain any real secrets itself - it reads them from environment variables at startup, via a local `.env` file that's never committed to git. You need to create that file and fill it in before the project will run.

### 6.1 Copy the example file

In the project root (same folder as `manage.py`), copy `.env.example` to a new file named exactly `.env`:

```bash
# macOS / Linux
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env
```

`.env.example` is committed to the repo as a template with placeholder values, so you always know what variables are needed. `.env` is your own local copy with real values, and `.gitignore` is already set up to keep it out of git.

### 6.2 Generate a secret key

`DJANGO_SECRET_KEY` is what Django uses to cryptographically sign session cookies, password reset tokens, and CSRF tokens - every developer running this project needs their own, and it should never be shared or reused across machines. Generate one with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

This prints a random string like `k8#p2m...`. Copy it into your `.env` file as the value for `DJANGO_SECRET_KEY`.

### 6.3 Fill in the rest of `.env`

Open `.env` in a text editor and fill in the remaining values:

```ini
DJANGO_SECRET_KEY=<the key you generated above>
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=

DB_NAME=newsfeedapp_db
DB_USER=root
DB_PASSWORD=<your MySQL password>
DB_HOST=localhost
DB_PORT=
```

- **`DJANGO_SECRET_KEY`** - the key from step 6.2. Required; the project won't start without it.
- **`DJANGO_DEBUG`** - `True` for local development (shows detailed error pages). Leave as `True` for this setup; only ever set to `False` in a real deployment.
- **`DJANGO_ALLOWED_HOSTS`** - a comma-separated list of hostnames allowed to serve the app. Leave blank for local development.
- **`DB_NAME`** - the database you created in step 5. Leave as `newsfeedapp_db` unless you named it something else.
- **`DB_USER`** / **`DB_PASSWORD`** - **your own** MySQL username and password. If you created a MySQL user other than `root` for this project, use that username instead.
- **`DB_HOST`** / **`DB_PORT`** - leave as shown above unless MySQL is running somewhere other than your own machine, or on a non-default port.

No quotes around any of the values - everything after the `=` is read literally.

> **Security note:** `.env` holds real credentials and should never be committed or shared. If you ever do accidentally commit it, treat every value inside as compromised - rotate your MySQL password and generate a fresh secret key, rather than just removing the file from a later commit.

## 7. Apply migrations

This creates all the necessary tables in your new database:

```bash
python manage.py makemigrations
python manage.py migrate
```

## 8. (Optional) Create an admin superuser

The Django admin panel (`/admin/`) is used for maintenance only - day-to-day features like creating publishers happen inside the app itself, not here. A superuser is still useful for inspecting/fixing data:

```bash
python manage.py createsuperuser
```

Follow the prompts to set a username, email, and password.

## 9. Run the development server

```bash
python manage.py runserver
```

You should see output ending in something like:

```
Starting development server at http://127.0.0.1:8000/
```

## 10. Access the app

Open your browser and go to:

```
http://127.0.0.1:8000/
```

This loads the login page. From there:
1. Click through to **register** a new account and choose a role (Reader, Journalist, or Editor).
2. Log in - you'll land on the welcome page with links to Articles, Newsletters, Publishers, and Journalists.
3. **If you registered as an Editor:** go to **Publishers** to create a new publisher (you'll be assigned to it automatically), then use that publisher's page to assign journalists to it.

The Django admin panel, if you created a superuser, is available at `http://127.0.0.1:8000/admin/`.

---

## Running with Docker

Docker runs the app and its MariaDB database in containers, so you don't need Python, MySQL, or a virtual environment on your machine - only Docker. The project includes a `Dockerfile` (builds the Django app image) and a `docker-compose.yml` (runs the app and the database together).

### Docker prerequisites

- **Docker** with Docker Compose - on Windows and macOS, install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Compose is included); on Linux, install Docker Engine and the Compose plugin.
- **Git**

Check that Docker is installed:

```bash
docker --version
docker compose version
```

(Very old Docker installations use `docker-compose` with a hyphen instead of `docker compose`.)

### Clone the project

Follow steps 1 and 2 above to clone the project and enter the folder. Make sure your terminal is in the folder containing both `manage.py` and `docker-compose.yml`.

### Create your `.env` file

Copy the example file, exactly as in step 6.1:

```bash
# macOS / Linux
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env
```

Then generate a secret key. Use this command rather than the one in step 6.2 - it only produces letters, digits, `-` and `_`, whereas Django's own generator can output `$`, which Docker Compose treats as a special character in `.env` files:

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
```

(If you have Python installed locally, `python -c "import secrets; print(secrets.token_urlsafe(50))"` does the same thing.)

Open `.env` and fill it in:

```ini
DJANGO_SECRET_KEY=<the key you generated above>
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=

DB_NAME=newsfeedapp_db
DB_USER=root
DB_PASSWORD=<choose a password>
DB_HOST=localhost
DB_PORT=
```

- **`DJANGO_DEBUG`** - keep this as `True`. The container uses Django's development server, which only serves static files (such as the site's CSS) in debug mode.
- **`DB_NAME`** - leave as `newsfeedapp_db`. The database container creates it for you; there's no need to create it by hand as in step 5.
- **`DB_USER`** - keep this as `root`. The database container is created with `root` as its only user.
- **`DB_PASSWORD`** - choose any password. The database container is created with it the first time it starts, so you're setting a new password here, not entering an existing one. Avoid `$` characters. If you change it later, run `docker compose down -v` first (see below), because the database keeps the password it was first created with.
- **`DB_HOST`** / **`DB_PORT`** - leave as shown. Docker Compose overrides `DB_HOST` so the app finds the database container, and the default port is used.

### Build and start the containers

```bash
docker compose up --build
```

The first run downloads the base images and builds the app image, which can take a few minutes. After that, Docker starts the database, waits until it's ready, applies the migrations automatically, and starts the server. It's ready when you see output like:

```
Starting development server at http://0.0.0.0:8000/
```

### Open the app

Go to `http://127.0.0.1:8000/` in your browser. (The `0.0.0.0` in the log output isn't an address you can browse to.) From here, follow step 10 above to register an account and start using the app.

### (Optional) Create an admin superuser

Open a second terminal in the project folder and run:

```bash
docker compose exec web python manage.py createsuperuser
```

### Everyday commands

| Task | Command |
|------|---------|
| Stop the app | `Ctrl+C` in the terminal running it, then `docker compose down` (your data is kept) |
| Start it again | `docker compose up` |
| Start in the background | `docker compose up -d` |
| View the app's output and logs | `docker compose logs -f web` |
| Rebuild after changing code or settings | `docker compose up --build` |
| Run the tests | `docker compose exec web python manage.py test` |
| Stop and delete all data, including the database | `docker compose down -v` |

Your code is copied into the image when it's built, so edits aren't picked up until you rebuild with `docker compose up --build`.

The "article approved" and password-reset emails (see the notes below) print to the app container's output - in the terminal running `docker compose up`, or via `docker compose logs -f web` if you started it in the background.

---

## Notes on email and the "approved article" API

- **Password resets and "article approved" notifications currently print to your terminal** instead of sending real emails - this project uses Django's console email backend by default. To send real emails instead, edit the `# Email` section at the bottom of `settings.py`: set `EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'` and add `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `EMAIL_USE_TLS` for your email provider. `EMAIL_HOST_PASSWORD` is a real credential, so follow the same pattern as the database settings above: add it to `.env` and read it via `os.environ`, rather than writing it directly into `settings.py`.
- The internal `/api/approved/` endpoint (used to simulate sharing a newly-approved article with a third party) works out of the box with no extra configuration.

## Running tests

```bash
python manage.py test
```

If you're running with Docker, use `docker compose exec web python manage.py test` instead.
