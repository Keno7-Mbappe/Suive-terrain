"""
Django settings for the PDCED - Skills project.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-key-change-in-production")

DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# Render (et la plupart des PaaS) terminent le TLS au niveau de leur proxy et
# relaient en HTTP simple vers l'application, avec cet en-tête pour indiquer
# que la requête d'origine était bien en HTTPS. Sans ça, `request.is_secure()`
# renvoie toujours False derriere le proxy (cookies de session non securises,
# CSRF qui echoue sur les formulaires).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.referentiels",
    "apps.comptes",
    "apps.beneficiaires",
    "apps.formations",
    "apps.certifications",
    "apps.insertions",
    "apps.suivis",
    "apps.satisfactions",
    "apps.imports",
    "apps.dashboard",
    "apps.reporting",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# By default falls back to local SQLite so `runserver` works before Supabase
# credentials are configured. Set DATABASE_URL in .env to point to Supabase
# Postgres, e.g.:
# DATABASE_URL=postgresql://postgres:<password>@<host>.supabase.co:5432/postgres
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        # conn_health_checks : le pooler Supabase (Supavisor) ferme parfois une
        # connexion persistante cote serveur sans prevenir Django - sans ce
        # controle, la requete suivante echoue avec "server closed the
        # connection unexpectedly". Django verifie la connexion avant reutilisation
        # et en ouvre une nouvelle si necessaire, au lieu de planter.
        "default": dj_database_url.parse(
            DATABASE_URL, conn_max_age=600, conn_health_checks=True, ssl_require=True
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"

TIME_ZONE = "Africa/Djibouti"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Le stockage "manifest" (cache-busting par hash) exige un `collectstatic` préalable :
# on ne l'active qu'en production, sinon `runserver`/les tests cassent tant qu'il n'a
# pas été exécuté.
STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "login"

# --- KoboToolbox integration ---
KOBO_API_BASE_URL = os.environ.get("KOBO_API_BASE_URL", "https://kf.kobotoolbox.org")
KOBO_API_TOKEN = os.environ.get("KOBO_API_TOKEN", "")
KOBO_ASSET_UID_SUIVI = os.environ.get("KOBO_ASSET_UID_SUIVI", "")
KOBO_ASSET_UID_SATISFACTION = os.environ.get("KOBO_ASSET_UID_SATISFACTION", "")
KOBO_ASSET_UID_SATISFACTION_INSTITUTION = os.environ.get("KOBO_ASSET_UID_SATISFACTION_INSTITUTION", "")

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}

CORS_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
