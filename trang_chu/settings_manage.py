from .settings import *  # noqa: F403,F401

# Management commands on Windows can fail if dashboard.log is locked by a running process.
# Use console logging only for admin tasks like migrate.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

