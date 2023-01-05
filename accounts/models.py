import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as BaseManager
from django.contrib.gis.geos import Point
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.functional import cached_property
from phonenumber_field.modelfields import PhoneNumberField
from phonenumber_field.phonenumber import to_python

from noiseworks import cobrand
from noiseworks.message import send_email


class UserManager(BaseManager):
    def create_user(self, username=None, **extra_fields):
        username = username or str(uuid.uuid4())
        return super().create_user(username, **extra_fields)

    def _create_user(self, username, email, password, phone="", **extra_fields):
        if not username:
            raise ValueError("The given username must be set")  # pragma: no cover

        phone_verified = False
        email_verified = False
        phone_parsed = to_python(phone)
        if phone_parsed and phone_parsed.is_valid():
            phone = phone_parsed
            phone_verified = True
        if email and "@" in email:
            email = self.normalize_email(email)
            email_verified = True

        user = super()._create_user(
            username,
            email,
            password,
            phone=phone,
            email_verified=email_verified,
            phone_verified=phone_verified,
            **extra_fields,
        )
        return user

    def check_existing(self, email=None, phone=None):
        if email:
            try:
                return User.objects.get(email=email, email_verified=True)
            except User.DoesNotExist:
                pass
        if phone:
            try:
                return User.objects.get(phone=phone, phone_verified=True)
            except User.DoesNotExist:
                pass
        return None


class User(AbstractUser):
    BEST_METHOD_CHOICES = [
        ("email", "Email"),
        ("phone", "Phone"),
    ]
    BEST_TIME_CHOICES = [
        ("weekday", "Weekdays"),
        ("weekend", "Weekends"),
        ("evening", "Evenings"),
    ]
    ESTATE_CHOICES = [
        ("y", "Yes"),
        ("n", "No"),
        ("?", "Don’t know"),
    ]

    phone = PhoneNumberField(blank=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    # Complainant things
    uprn = models.CharField(max_length=20, blank=True)
    estate = models.CharField(max_length=1, choices=ESTATE_CHOICES, blank=True)
    address = models.TextField(blank=True)
    best_time = ArrayField(
        models.CharField(max_length=7, choices=BEST_TIME_CHOICES),
        size=3,
        null=True,
        blank=True,
    )
    best_method = models.CharField(
        choices=BEST_METHOD_CHOICES, max_length=5, null=True, blank=True
    )
    # For complainants and perpetrators
    contact_warning = models.TextField(blank=True, null=True)
    # Staff things
    wards = ArrayField(
        models.CharField(max_length=9),
        null=True,
        blank=True,
    )
    principal_wards = ArrayField(models.CharField(max_length=9), default=list)
    staff_email_notifications = models.BooleanField(default=True)
    staff_web_notifications = models.BooleanField(default=True)

    objects = UserManager()

    class Meta:
        ordering = ("first_name", "last_name")
        constraints = [
            models.UniqueConstraint(
                name="unique_email",
                fields=["email"],
                condition=models.Q(email_verified=True),
            ),
            models.UniqueConstraint(
                name="unique_phone",
                fields=["phone"],
                condition=models.Q(phone_verified=True),
            ),
        ]
        permissions = [
            ("edit_contact_warning", "Can add, remove or edit a contact warning."),
        ]

    def __str__(self):
        name = self.get_full_name() or self.email or self.username
        if self.address:
            name += f", {self.address}"
        return name

    def save(self, *args, **kwargs):
        self.update_address_and_estate()
        self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def update_address_and_estate(self):
        if self.uprn and not (self.address and self.estate):
            addr = cobrand.api.address_for_uprn(self.uprn)
            if addr["string"]:
                if not self.address:
                    self.address = addr["string"]
                if not self.estate:
                    point = Point(addr["longitude"], addr["latitude"], srid=4326)
                    estate = cobrand.api.in_an_estate(point)
                    self.estate = "y" if estate else "n"

    def get_best_time_display(self):
        best_time = self.best_time or []
        choices_dict = dict(self.BEST_TIME_CHOICES)
        return list(map(choices_dict.get, best_time))

    @property
    def address_display(self):
        return self.address or self.uprn or "Unknown location"

    @cached_property
    def number_cases_involved(self):
        perpetrated = self.cases_perpetrated.count()
        reporting = self.complaints.aggregate(models.Count("case", distinct=True))
        return perpetrated + reporting["case__count"]

    @cached_property
    def unread_notifications_count(self):
        return self.notifications.filter(read=False).count()

    def get_wards_display(self):
        principal_wards = self.principal_wards if self.principal_wards else []
        wards = self.wards if self.wards else []

        if not wards and not principal_wards:
            return "No wards"

        ward_mappings = cobrand.api.wards()
        ward_gss_to_name = {w["gss"]: w["name"] for w in ward_mappings}

        ward_principal_names = [
            ward_gss_to_name.get(w) + " (principal)" for w in principal_wards
        ]
        assigned_ward_names = [
            ward_gss_to_name.get(w) for w in wards if w not in principal_wards
        ]

        return ", ".join(ward_principal_names + assigned_ward_names)

    def send_email(self, *args, **kwargs):
        if not self.is_staff:
            raise Exception("Not implemented for non-staff users.")
        if not self.staff_email_notifications:
            return
        send_email(self.email, *args, **kwargs)
