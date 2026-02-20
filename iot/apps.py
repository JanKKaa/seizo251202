from django.apps import AppConfig

class IotConfig(AppConfig):
    name = "iot"
    verbose_name = "IoT"

    def ready(self):
        from . import signals  # noqa