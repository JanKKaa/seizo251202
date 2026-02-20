from django.apps import AppConfig

class TrangChuConfig(AppConfig):
    name = 'trang_chu'

    def ready(self):
        import trang_chu.signals