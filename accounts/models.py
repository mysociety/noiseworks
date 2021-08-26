from django.contrib.auth.models import AbstractUser, UserManager as BaseManager
from django.contrib.postgres.fields import ArrayField
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from phonenumber_field.phonenumber import to_python


class UserManager(BaseManager):
    def _create_user(self, username, email, password, phone="", **extra_fields):
        if not username:
            raise ValueError("The given username must be set")  # pragma: no cover

        phone_verified = False
        email_verified = False
        phone_parsed = to_python(username)
        if phone_parsed.is_valid():
            phone = phone_parsed
            username = str(phone)
            phone_verified = True
        elif "@" in username:
            email = username
            username = self.normalize_email(email)
            email_verified = True

        user = super()._create_user(
            username,
            email,
            password,
            phone=phone,
            email_verified=email_verified,
            phone_verified=phone_verified,
            **extra_fields
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

    def __str__(self):
        return self.get_full_name() or self.username

    def get_best_time_display(self):
        best_time = self.best_time or []
        choices_dict = dict(self.BEST_TIME_CHOICES)
        return list(map(choices_dict.get, best_time))
