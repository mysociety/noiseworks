"""
Django settings for noiseworks project.

Generated by 'django-admin startproject' using Django 3.2.3.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

import environ
from pathlib import Path
import pgconnection
from noiseworks.sass import inline_image


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

if env.str("BUGS_EMAIL", None):  # pragma: no cover
    SERVER_EMAIL = env("BUGS_EMAIL")
    ADMINS = (("mySociety bugs", env("BUGS_EMAIL")),)

ALLOWED_HOSTS = env("ALLOWED_HOSTS")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INTERNAL_IPS = ["127.0.0.1"]

# Application definition

COBRAND = env("COBRAND")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.gis",
    "compressor",
    "debug_toolbar",
    "pgconnection",
    "pgtrigger",
    "crispy_forms",
    "django_filters",
    "accounts",
    "oauth",
    "cases",
    COBRAND,
    "crispy_forms_gds",
]

CRISPY_ALLOWED_TEMPLATE_PACKS = ("gds",)
CRISPY_TEMPLATE_PACK = "gds"
CRISPY_CLASS_CONVERTERS = {
    "select": "govuk-select lbh-select",
    "textinput": "govuk-input lbh-input",
    "emailinput": "govuk-input lbh-input",
    "timewidget": "govuk-input lbh-input govuk-input--width-5",
    "textarea": "govuk-textarea lbh-textarea",
    "clearablefileinput": "govuk-file-upload lbh-file-upload",
    "searchwidget": "govuk-input lbh-input",
}

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "noiseworks.middleware.user_audit_middleware",
]

ROOT_URLCONF = "noiseworks.urls"

APPEND_SLASH = False

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "noiseworks" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "noiseworks.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = pgconnection.configure(
    {
        "default": env.db(),
    }
)

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
if DEBUG:  # pragma: no cover
    AUTH_PASSWORD_VALIDATORS = []

AUTHLIB_OAUTH_CLIENTS = {
    "google": {
        "client_id": env.str("OAUTH_CLIENT_ID", None),
        "client_secret": env.str("OAUTH_CLIENT_SECRET", None),
        "authorize_params": {
            "hd": env.str("OAUTH_CLIENT_DOMAIN", None),
        },
    }
}

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "sesame.backends.ModelBackend",
]

LOGIN_URL = "/a"

SESAME_MAX_AGE = 300
SESAME_ONE_TIME = False
SESAME_SIGNATURE_SIZE = 5

# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

PHONENUMBER_DEFAULT_REGION = "GB"

LANGUAGE_CODE = "en-gb"

TIME_ZONE = "Europe/London"

USE_I18N = True

USE_L10N = False
DATETIME_FORMAT = "D, j M Y, P"
DATE_FORMAT = "D, j M Y"
TIME_INPUT_FORMATS = [
    "%I:%M %p",
    "%I.%M %p",
    "%I %M %p",
    "%I:%M%p",
    "%I.%M%p",
    "%I %M%p",
    "%I %p",
    "%I%p",
]

FILTERS_EMPTY_CHOICE_LABEL = "Any"

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / ".static"

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
)

STATICFILES_DIRS = [BASE_DIR / "noiseworks" / "static"]

COMPRESS_PRECOMPILERS = (("text/x-scss", "django_libsass.SassCompiler"),)

LIBSASS_CUSTOM_FUNCTIONS = {
    "inline-image": inline_image,
}
LIBSASS_ADDITIONAL_INCLUDE_PATHS = [
    "/opt/npmsetup",  # XXX For docker-compose
    str(BASE_DIR / COBRAND),
]

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

COBRAND_SETTINGS = {
    "address_api": {
        "url": env.str("ADDRESS_API_URL", "https://example.com/"),
        "pageAttr": env.str("ADDRESS_API_PAGEATTR", "page_count"),
        "key": env.str("ADDRESS_API_KEY", "key"),
    }
}

# Sending messages

EMAIL_HOST = env.str("EMAIL_HOST", "localhost")
EMAIL_PORT = env.str("EMAIL_PORT", 1025)
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", "")

MAPIT_API_KEY = env.str("MAPIT_API_KEY", None)

NOTIFY_API_KEY = env.str("NOTIFY_API_KEY", None)
NOTIFY_TEMPLATE_ID = env.str("NOTIFY_TEMPLATE_ID", None)
