from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Machine, MachineStatusEvent, STATUS_CHOICES

STATUS_MAP = dict(STATUS_CHOICES)

@receiver(pre_save, sender=Machine)
def machine_status_change(sender, instance: Machine, **kwargs):
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.status != instance.status:
        MachineStatusEvent.objects.create(
            machine=instance,
            status_code=instance.status,
            status_jp=STATUS_MAP.get(instance.status,"不明")
        )