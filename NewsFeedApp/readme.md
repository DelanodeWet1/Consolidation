# NewsFeedApp

A Django news platform with three account roles - **Reader**, **Journalist**, and **Editor** - split across two apps:

- **AuthApp** - registration, login, logout, and password reset
- **ArticlesAndMore** - articles, newsletters, publishers, journalist/reader subscriptions, and a small token-authenticated REST API

This guide assumes no prior Django experience. Follow the steps in order, copying and pasting the commands for your operating system.

You may find the project avialable for download at the following public repo: https://github.com/DelanodeWet1/NewsFeedApp

## Prerequisites

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

## Notes on email and the "approved article" API

- **Password resets and "article approved" notifications currently print to your terminal** instead of sending real emails - this project uses Django's console email backend by default. To send real emails instead, edit the `# Email` section at the bottom of `settings.py`: set `EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'` and add `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `EMAIL_USE_TLS` for your email provider. `EMAIL_HOST_PASSWORD` is a real credential, so follow the same pattern as the database settings above: add it to `.env` and read it via `os.environ`, rather than writing it directly into `settings.py`.
- The internal `/api/approved/` endpoint (used to simulate sharing a newly-approved article with a third party) works out of the box with no extra configuration.

## Running tests

```bash
python manage.py test
```
