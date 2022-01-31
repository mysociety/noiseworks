from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Action, Complaint


@receiver(post_save, sender=Complaint)
@receiver(post_save, sender=Action)
def update_case(sender, instance, **kwargs):
    # Update the case last modified
    instance.case.save()
