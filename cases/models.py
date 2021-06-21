from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.urls import reverse
from accounts.models import User


class AbstractModel(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)ss",
        editable=False,
    )
    modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="modified_%(class)s_set",
        editable=False,
    )

    class Meta:
        abstract = True


class Case(AbstractModel):
    KIND_CHOICES = [
        ("car", "Car alarm"),
        ("diy", "DIY"),
        ("dog", "Dog barking"),
        ("alarm", "House / intruder alarm"),
        ("music", "Music"),
        ("road", "Noise on the road"),
        ("shouting", "Shouting"),
        ("tv", "TV"),
        ("other", "Other"),
    ]
    WHERE_CHOICES = [
        (
            "business",
            "A shop, bar, nightclub, building site or other commercial premises",
        ),
        ("residence", "A house, flat, park or street"),
    ]
    ESTATE_CHOICES = [
        ("y", "Yes"),
        ("n", "No"),
        ("?", "Don’t know"),
    ]

    # Type
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    kind_other = models.CharField(max_length=100, blank=True)

    # Location
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    radius = models.IntegerField(blank=True, null=True)
    uprn = models.CharField(max_length=20, blank=True)
    where = models.CharField(max_length=9, choices=WHERE_CHOICES)
    estate = models.CharField(max_length=1, choices=ESTATE_CHOICES)

    assigned = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="assignations",
    )

    class Meta:
        ordering = ("-id",)

    def get_absolute_url(self):
        return reverse("case-view", args=[self.pk])

    @property
    def kind_display(self):
        if self.kind == "other":
            return self.kind_other
        else:
            return self.get_kind_display()

    def location_display(self):
        if self.uprn:
            return self.uprn
        else:
            return f"{self.radius}m around ({self.latitude},{self.longitude})"


class Complaint(AbstractModel):
    DAY_CHOICES = [
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ]
    TIME_CHOICES = [
        ("morning", "Morning (6am – noon)"),
        ("daytime", "Daytime (noon – 6pm)"),
        ("evening", "Evening (6pm – 11pm)"),
        ("night", "Night time (11pm – 6am)"),
    ]

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="complaints")
    happening_now = models.BooleanField()
    happening_pattern = models.BooleanField()
    happening_days = ArrayField(
        models.PositiveSmallIntegerField(choices=DAY_CHOICES),
        size=7,
        null=True,
        blank=True,
    )
    happening_times = ArrayField(
        models.CharField(max_length=7, choices=TIME_CHOICES),
        size=4,
        null=True,
        blank=True,
    )
    happening_description = models.TextField(blank=True)
    more_details = models.TextField(blank=True)
