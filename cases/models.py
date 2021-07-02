from django.db import models
from django.db.models import Q
from django.contrib.postgres.fields import ArrayField
from django.urls import reverse
from django.utils.functional import cached_property
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


class CaseManager(models.Manager):
    def unmerged(self):
        q = Q(action__isnull=True) | Q(action__case_old_id__isnull=True)
        qs = self.filter(q).select_related("assigned")
        return qs


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

    objects = CaseManager()

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

    @cached_property
    def merged_into_list(self) -> list:
        """Return a list of the IDs of the Cases that this has been merged into, if any."""
        query = Action.objects.raw(
            """WITH RECURSIVE cte AS (
                SELECT id,case_old_id,case_id FROM cases_action WHERE case_old_id = %s
                UNION
                SELECT s.id,s.case_old_id,s.case_id FROM cte JOIN cases_action s ON cte.case_id = s.case_old_id
            )
            SELECT * FROM cte """,
            [self.id],
        )

        merged = []
        for action in query:
            merged.append({"id": action.case_id, "at": action.created})
        return merged

    @cached_property
    def merged_into(self):
        """Return the ID of the final Case that this has been merged into, if any."""
        merged = self.merged_into_list
        merged = merged[-1]["id"] if merged else None
        return merged

    @cached_property
    def timeline(self):
        data = []
        for action in self.actions_reversed:
            row = {
                "time": action.created,
                "summary": str(action),
            }
            data.append(row)
        complaints = self.complaints.all()
        for complaint in complaints:
            row = {
                "time": complaint.created,
                "summary": f"{complaint.created_by} submitted a complaint",
            }
            data.append(row)
        data = sorted(data, reverse=True, key=lambda x: x["time"])
        return data

    @cached_property
    def actions_reversed(self):
        actions = Action.objects.get_merged_cases([self])
        query = Q(case__in=actions.keys())
        for merged in self.merged_into_list:
            query |= Q(created__gte=merged["at"], case=merged["id"])
        actions = Action.objects.filter(query)
        actions = actions.order_by("-created")
        return actions

    @property
    def last_action(self):
        return self.actions_reversed[0] if len(self.actions_reversed) else None


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


class ActionType(models.Model):
    name = models.CharField(max_length=100)
    common = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class ActionManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related(
            "created_by", "case", "type", "assigned_old", "assigned_new", "case_old"
        )
        return qs

    def get_reversed(self, merge_map):
        """Given a mapping of merged/unmerged case IDs, return a mapping of the
        actions of those cases."""
        case_ids = merge_map.keys()
        actions_reversed = self.filter(case__in=case_ids).order_by("-created")
        actions_by_case = {}
        for action in actions_reversed:
            merged_case_id = merge_map[action.case_id]
            actions_by_case.setdefault(merged_case_id, []).append(action)
        return actions_by_case

    def get_merged_cases(self, cases):
        """Given a list of Case IDs, returns a dict mapping other Cases that have
        been merged into those Cases."""
        case_ids = map(lambda x: str(x.id), cases)
        case_ids = ",".join(case_ids)
        if not case_ids:
            return {}
        query = self.raw(
            """WITH RECURSIVE cte AS (
                SELECT s.id,s.case_old_id,s.case_id FROM cases_action s WHERE s.case_id IN (%s) AND s.case_old_id IS NOT NULL
                UNION
                SELECT s.id,s.case_old_id,cte.case_id FROM cte JOIN cases_action s ON cte.case_old_id = s.case_id AND s.case_old_id IS NOT NULL
            )
            SELECT * FROM cte """
            % case_ids,
        )

        merge_map = {c.id: c.id for c in cases}
        for action in query:
            merge_map[action.case_old_id] = action.case_id
        return merge_map


class Action(AbstractModel):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="actions")

    # User
    type = models.ForeignKey(
        ActionType,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="actions",
    )
    notes = models.TextField(blank=True)

    # Reassign
    assigned_old = models.ForeignKey(
        User, blank=True, null=True, on_delete=models.PROTECT, related_name="+"
    )
    assigned_new = models.ForeignKey(
        User, blank=True, null=True, on_delete=models.PROTECT, related_name="+"
    )

    # Merge
    case_old = models.ForeignKey(Case, blank=True, null=True, on_delete=models.PROTECT)

    objects = ActionManager()

    def __str__(self):
        old = self.assigned_old
        new = self.assigned_new
        if self.assigned_old and self.assigned_new:
            return (
                f"{self.created_by} reassigned case {self.case_id} from {old} to {new}"
            )
        elif self.assigned_new:
            return f"{self.created_by} assigned {new} to case {self.case_id}"
        elif self.assigned_old:
            return f"{self.created_by} unassigned {old} from case {self.case_id}"
        elif self.case_old:
            return f"{self.created_by} merged case {self.case_old_id} into case {self.case_id}"
        elif self.type:
            return f"{self.created_by}, {self.type.name}, case {self.case_id}"
        else:
            return f"{self.created_by}, case {self.case_id}, unknown action"
