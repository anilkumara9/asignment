"""
Django settings for the Spotter fuel-route API assessment project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# For a real deployment set the DJANGO_SECRET_KEY environment variable.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-2_)ab-3q8+=v^bk!b^bz1+-!a%%v4qy=o-%m*r+%!_f9k49zk7",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = ["*"] if DEBUG else os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# Application definition

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "fuelrouter",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# This API is stateless; sqlite is only here so Django is happy.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Cache: external API results (geocoding + routing) live here so we call the
# free map/routing APIs as rarely as possible — ideally once per unique route.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fuelrouter-cache",
        "TIMEOUT": 60 * 60 * 24,  # 24 hours
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"

# ---------------------------------------------------------------------------
# Fuel-route planner tunables (assignment defaults)
# ---------------------------------------------------------------------------
MPG = 10                    # vehicle fuel efficiency, miles per gallon
MAX_RANGE_MILES = 500       # vehicle maximum range on a full tank
STATION_CAPTURE_MILES = 10  # a fuel station counts as "along the route" if it
                            # is within this many miles of the route polyline

# Free external services used (no API key required)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}
