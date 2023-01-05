from django.db.models.signals import post_save
from django.dispatch import receiver, Signal

from accounts.models import User
from noiseworks import cobrand
from noiseworks.message import send_email

from .models import Action, Case, Complaint, MergeRecord

new_case_reported = Signal()


@receiver(new_case_reported)
def auto_assign_new_case(sender, case, case_absolute_url, **kwargs):
    if case.assigned or case.estate == "y" or not case.ward:
        return
    ward_principal = User.objects.filter(principal_wards__contains=[case.ward]).first()

    if not ward_principal:
        return

    case.assign(ward_principal, None)
    case.save()

    wards = cobrand.api.wards()
    ward_gss_to_name = {ward["gss"]: ward["name"] for ward in wards}
    ward_name = ward_gss_to_name.get(case.ward, case.ward)
    ward_principal.send_email(
        "You have been assigned",
        "cases/email/auto_assigned",
        {
            "case": case,
            "url": case_absolute_url,
            "user": ward_principal,
            "ward_name": ward_name,
        },
    )


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
