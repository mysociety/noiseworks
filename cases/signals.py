from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Action, Case, Complaint, MergeRecord


@receiver(post_save, sender=Complaint)
def update_case_for_complaint(sender, instance, created, **kwargs):
    if created:
        instance.case.last_update_type = Case.LastUpdateTypes.COMPLAINT

    # Update the case last modified
    instance.case.save()


@receiver(post_save, sender=Action)
def update_case_for_action(sender, instance, **kwargs):
    # Action took place before the case was last
    # modified so don't update it
    if instance.time < instance.case.modified:
        return

    instance.case.last_update_type = Case.LastUpdateTypes.ACTION

    # Update the case last modified
    instance.case.save()


@receiver(post_save, sender=MergeRecord)
def update_case_for_merge_record(sender, instance, created, **kwargs):
    if created:
        instance.mergee.last_update_type = Case.LastUpdateTypes.MERGE

    # Update the case last modified
    instance.mergee.save()
    instance.merged_into.save()
