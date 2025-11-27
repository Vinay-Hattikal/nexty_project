"""
Django settings for nexty project.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------
# Basic / environment
# -------------------------
SECRET_KEY = os.environ.get('NEXTY_SECRET_KEY', 'django-insecure-dev-secret-for-local')

DEBUG = os.environ.get('NEXTY_DEBUG', 'True').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = (
    os.environ.get('NEXTY_ALLOWED_HOSTS', '')
    .split(',') if os.environ.get('NEXTY_ALLOWED_HOSTS') else []
)


# -------------------------
# Installed apps / middleware
# -------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # your apps
    'accounts',
    'jobs',
    'interview',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nexty.urls'


# -------------------------
# Templates
# -------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.static',   # for {% static %} helper
                'django.template.context_processors.media',    # makes MEDIA_URL available in templates
                'django.template.context_processors.csrf',     # makes csrf_token available
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'nexty.wsgi.application'


# -------------------------
# Database (sqlite for dev)
# -------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# -------------------------
# Password validation
# -------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# -------------------------
# Internationalization
# -------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('NEXTY_TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True


# -------------------------
# Static & media
# -------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.environ.get('NEXTY_STATIC_ROOT', os.path.join(BASE_DIR, 'staticfiles'))

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# -------------------------
# Auth
# -------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/dashboard-redirect/'
LOGOUT_REDIRECT_URL = '/accounts/login/'


# -------------------------
# Email configuration
# -------------------------
# Default: console backend in development (prints emails to terminal)
EMAIL_BACKEND = os.environ.get('NEXTY_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.environ.get('NEXTY_DEFAULT_FROM_EMAIL', 'Nexty <no-reply@nexty.local>')

# Allow shorthand NEXTY_EMAIL_BACKEND='smtp' for convenience
if EMAIL_BACKEND.lower() in ('smtp', 'django.core.mail.backends.smtp.emailbackend', 'django.core.mail.backends.smtp.EmailBackend'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('NEXTY_EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('NEXTY_EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.environ.get('NEXTY_EMAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes')
    EMAIL_HOST_USER = os.environ.get('NEXTY_EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('NEXTY_EMAIL_HOST_PASSWORD', '')
else:
    # leave other backends as-is (console, file, etc.)
    EMAIL_HOST = os.environ.get('NEXTY_EMAIL_HOST', '')
    EMAIL_PORT = os.environ.get('NEXTY_EMAIL_PORT', '')
    EMAIL_USE_TLS = os.environ.get('NEXTY_EMAIL_USE_TLS', '')
    EMAIL_HOST_USER = os.environ.get('NEXTY_EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('NEXTY_EMAIL_HOST_PASSWORD', '')

if DEBUG and EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
    print("INFO: Using console email backend (emails printed to terminal).")


# -------------------------
# Logging (basic)
# -------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO' if DEBUG else 'WARNING',
            'propagate': False,
        },
    },
}


# -------------------------
# Security (production suggestions)
# -------------------------
# In production, you should set these via environment variables:
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_BROWSER_XSS_FILTER = True

# -------------------------
# End of settings.py
# -------------------------
