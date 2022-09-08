from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Action, Complaint


@receiver(post_save, sender=Complaint)
def update_case_for_complaint(sender, instance, **kwargs):
    # Update the case last modified
    instance.case.save()


@receiver(post_save, sender=Action)
def update_case_for_action(sender, instance, **kwargs):
    # Action took place before the case was last
    # modified so don't update it
    if instance.time < instance.case.modified:
        return

    # Update the case last modified
    instance.case.save()
