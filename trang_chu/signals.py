from django.db.models.signals import post_save
from django.db.backends.signals import connection_created
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    instance.userprofile.save()


@receiver(connection_created)
def set_sqlite_pragma(sender, connection, **kwargs):
    """
    Keep SQLite conservative on the Windows bind mount.
    """
    if connection.vendor != "sqlite":
        return
    cursor = connection.cursor()
    cursor.execute("PRAGMA synchronous=FULL;")
    cursor.execute("PRAGMA busy_timeout=30000;")
