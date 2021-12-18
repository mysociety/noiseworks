import uuid
from django.contrib.auth.models import AbstractUser, UserManager as BaseManager
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.functional import cached_property
from phonenumber_field.modelfields import PhoneNumberField
from phonenumber_field.phonenumber import to_python
from noiseworks import cobrand


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

    phone = PhoneNumberField(blank=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    # Reporter things
    uprn = models.CharField(max_length=20, blank=True)
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
    # Staff things
    wards = ArrayField(
        models.CharField(max_length=9),
        null=True,
        blank=True,
    )

    objects = UserManager()

    class Meta:
        ordering = ("first_name", "last_name")

    def __str__(self):
        name = self.get_full_name() or self.email or self.username
        if self.address:
            name += f", {self.address}"
        return name

    def save(self, *args, **kwargs):
        self.update_address()
        return super().save(*args, **kwargs)

    def update_address(self):
        if not self.address and self.uprn:
            addr = cobrand.api.address_for_uprn(self.uprn)
            if addr["string"]:
                self.address = addr["string"]

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

    def get_wards_display(self):
        if not self.wards:
            return "No wards"
        wards = cobrand.api.wards()
        wards = {ward["gss"]: ward["name"] for ward in wards}
        wards = [wards.get(w) for w in self.wards]
        return ", ".join(wards)
