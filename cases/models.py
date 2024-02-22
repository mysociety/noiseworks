import requests
import math
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property, classproperty
from django.utils.html import format_html, mark_safe
from functools import lru_cache
from humanize import naturalsize
from simple_history.models import HistoricalRecords

from accounts.models import User
from noiseworks import cobrand
from noiseworks.current_user import get_current_user


def ward_name_to_id(ward):
    wards = cobrand.api.wards()
    wards = {ward["name"]: ward["gss"] for ward in wards}
    return wards.get(ward, "outside")


class AbstractModel(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_%(class)s_set",
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

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user:
            if not self.created_by:
                self.created_by = user
            self.modified_by = user
        super().save(*args, **kwargs)


class CaseSettingsSingleton(AbstractModel):
    _singleton = models.BooleanField(default=True, editable=False, unique=True)
    logged_action_editing_window = models.DurationField()
    max_file_storage_mb = models.FloatField()

    class Meta:
        verbose_name = "Case settings"
        verbose_name_plural = "Case settings"

    @classproperty
    @lru_cache(maxsize=None)
    def instance(cls):
        return cls.objects.all()[0]


class CaseManager(models.Manager):
    def unmerged(self):
        q = Q(merged_into__isnull=True)
        qs = self.filter(q).select_related("assigned")
        return qs

    def by_complainant(self, user):
        return self.filter(complaints__complainant=user).annotate(
            reoccurrences=Count("complaints") - 1
        )

    def prefetch_timeline_part(self, merge_map, qs, id_field):
        by_case = {}
        for obj in qs:
            merged_case_id = merge_map[getattr(obj, id_field)]
            by_case.setdefault(merged_case_id, []).append(obj)
        return by_case

    def prefetch_timeline(self, qs):
        """On a list page, we don't want to be fetching per-case actions,
        complaints, or histories. We can't use prefetch because a) that doesn't
        work on history anyway, and b) we've got the added complication of the
        merged cases to deal with."""

        merge_map = Case.objects.get_merged_cases(qs)
        case_ids = merge_map.keys()

        # Note that if case A is merged into case B, case A's actions_by_case
        # will not include case B's actions from after the merge.
        actions = Action.objects.filter(case__in=case_ids).order_by("-time")
        actions_by_case = self.prefetch_timeline_part(merge_map, actions, "case_id")
        merged_intos = Case.objects.get_merged_into_cases(qs)

        complaints = (
            Complaint.objects.filter(case__in=case_ids)
            .select_related("complainant")
            .order_by("-created")
        )
        complaints_by_case = self.prefetch_timeline_part(
            merge_map, complaints, "case_id"
        )

        histories = HistoricalCase.objects.filter(  # noqa: F821
            id__in=case_ids
        ).select_related("history_user", "assigned")
        self.attach_diffs(histories)
        histories_by_case = self.prefetch_timeline_part(merge_map, histories, "id")

        # Set the actions for each result to the right ones
        for case in qs:
            case.actions_reversed = actions_by_case.get(case.id, [])
            case.all_complaints_reversed = complaints_by_case.get(case.id, [])
            case.historical_entries = histories_by_case.get(case.id, [])
            case.merged_into_list = merged_intos.get(case.id)

    @staticmethod
    def attach_diffs(histories):
        histories_by_case = {}
        for history in histories:
            histories_by_case.setdefault(history.id, []).append(history)
        for case_id, edits in histories_by_case.items():
            edit = edits[0]
            edit._cached_diff = None
            for prev in edits[1:]:
                prev._cached_diff = edit.diff_against(
                    prev, excluded_fields=["last_update_type"]
                )
                edit = prev

    def get_merged_cases(self, cases):
        """Given a list of Case IDs, returns a dict mapping other Cases that have
        been merged into those Cases."""
        case_ids = map(lambda x: str(x.id), cases)
        case_ids = ",".join(case_ids)
        if not case_ids:
            return {}

        query = self.raw(
            """WITH RECURSIVE cte AS (
                 SELECT
                   c.id,
                   c.merged_into_id
                 FROM
                   cases_case c
                 WHERE
                   c.merged_into_id IN (%s)
                 UNION
                 SELECT
                   c.id,
                   cte.merged_into_id
                 FROM
                   cases_case c
                   JOIN cte ON cte.id = c.merged_into_id
               )
               SELECT
                 *
               FROM
                 cte
            """
            % case_ids,
        )

        merge_map = {c.id: c.id for c in cases}
        for entry in query:
            merge_map[entry.id] = entry.merged_into_id
        return merge_map

    def get_merged_into_cases(self, cases):
        """Given a list of Case IDs, returns a dict mapping those Cases into
        ones they have been merged into."""
        case_ids = map(lambda x: str(x.id), cases)
        case_ids = ",".join(case_ids)
        if not case_ids:
            return {}

        query = self.raw(
            """WITH RECURSIVE cte AS (
                 SELECT
                   m.mergee_id AS id,
                   m.merged_into_id,
                   m.time
                 FROM
                   cases_mergerecord m
                 WHERE
                   NOT m.unmerge
                   AND (
                     SELECT id
                     FROM cases_mergerecord m2
                     WHERE m2.id > m.id
                     AND m2.mergee_id = m.mergee_id
                     AND m2.merged_into_id = m.merged_into_id
                     LIMIT 1
                    ) IS NULL -- There are no later records.
                   AND m.mergee_id IN (%s)
                 UNION
                 SELECT
                   cte.id AS id,
                   m.merged_into_id,
                   m.time
                 FROM
                   cases_mergerecord m
                   JOIN cte ON m.mergee_id = cte.merged_into_id
                 WHERE
                   NOT m.unmerge
                   AND (
                     SELECT id
                     FROM cases_mergerecord m2
                     WHERE m2.id > m.id
                     AND m2.mergee_id = m.mergee_id
                     AND m2.merged_into_id = m.merged_into_id
                     LIMIT 1
                    ) IS NULL -- There are no later records.
               )
               SELECT
                 cte.id AS id,
                 cte.merged_into_id AS merged_into_id,
                 cte.time AS time
               FROM
                 cte
            """
            % case_ids,
        )

        merge_map = {c.id: [] for c in cases}
        for entry in query:
            merge_map[entry.id].append(
                {
                    "id": entry.merged_into_id,
                    "at": entry.time,
                }
            )
        return merge_map

    def annotate_total_complaints(self, qs):
        return qs.annotate(total_complaints=Count("complaints"))


class Case(AbstractModel):
    class LastUpdateTypes(models.TextChoices):
        ACTION = "AC", "Action"
        COMPLAINT = "CO", "Complaint"
        MERGE = "MR", "Merge"

    KIND_CHOICES = [
        ("animal", "Animal noise"),
        ("buskers", "Buskers"),
        ("car", "Car alarm"),
        ("construction", "Construction site noise"),
        ("deliveries", "Deliveries"),
        ("diy", "DIY"),
        ("alarm", "House / intruder alarm"),
        ("music-pub", "Music from pub"),
        ("music-club", "Music from club/bar"),
        ("music-other", "Music - other"),
        ("festival", "Noise caused by Religious Festivals"),
        ("roadworks", "Noise from roadworks"),
        ("road", "Noise on the road"),
        ("plant-machinery", "Plant noise - machinery"),
        ("plant-street", "Plant noise - machinery on street"),
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

    # State
    closed = models.BooleanField(default=False)
    merged_into = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="mergees",
    )

    # Type
    kind = models.CharField("Type", max_length=15, choices=KIND_CHOICES)
    kind_other = models.CharField("Other type", max_length=100, blank=True)

    # Location
    point = models.PointField(blank=True, null=True, srid=27700)
    radius = models.IntegerField(blank=True, null=True)
    uprn = models.CharField(max_length=20, blank=True)
    location_cache = models.CharField(max_length=200, blank=True)
    ward = models.CharField(max_length=9, blank=True)
    where = models.CharField(max_length=9, choices=WHERE_CHOICES)
    estate = models.CharField(max_length=1, choices=ESTATE_CHOICES, blank=True)

    # Internal Flags
    priority = models.BooleanField(default=False)
    review_date = models.DateField(blank=True, null=True)

    perpetrators = models.ManyToManyField(User, related_name="cases_perpetrated")

    assigned = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="assignations",
    )
    followers = models.ManyToManyField(User, related_name="cases_following")

    last_update_type = models.CharField(
        blank=True, max_length=2, choices=LastUpdateTypes.choices
    )

    history = HistoricalRecords(
        excluded_fields=["modified", "modified_by", "last_update_type"]
    )
    objects = CaseManager()

    class Meta:
        ordering = ("-modified", "-id")
        permissions = [
            (
                "edit_perpetrators",
                "Can add and remove perpetrators and edit their details",
            ),
            ("follow", "Can follow a case"),
            ("get_assigned", "Can get assigned to a case"),
            ("assign", "Can assign a case"),
            ("change_priority", "Can change priority"),
            ("change_review_date", "Can change review date"),
            ("merge", "Can merge and unmerge cases"),
        ]

    @property
    def _history_user(self):
        return self.modified_by

    @_history_user.setter
    def _history_user(self, value):
        self.modified_by = value  # pragma: no cover - not used?

    def get_absolute_url(self):
        return reverse("case-view", args=[self.pk])

    def save(self, *args, **kwargs):
        self.update_location_cache()
        return super().save(*args, **kwargs)

    def original_entry(self):
        r = self.reoccurrences
        case = self.history.earliest().instance
        case.reoccurrences = r
        return case

    def update_location_cache(self):
        if self.location_cache:
            pass
        elif self.uprn:
            addr = cobrand.api.address_for_uprn(self.uprn)
            if addr["string"]:
                self.location_cache = addr["string"]
                self.point = Point(addr["longitude"], addr["latitude"], srid=4326)
                self.ward = ward_name_to_id(addr["ward"])
        elif self.point:
            key = settings.MAPIT_API_KEY
            data = requests.get(
                f"https://mapit.mysociety.org/point/27700/{self.point.x},{self.point.y}?api_key={key}"
            ).json()
            if "2508" in data.keys():
                ward = ""
                for area in data.values():
                    if area["type"] == "LBW":
                        ward = area["codes"]["gss"]
                self.ward = ward

            park = cobrand.api.in_a_park(self.point)
            if park:
                desc = f"a point in {park['name']}"
            else:
                roads = cobrand.api.nearest_roads(self.point)
                if roads:
                    desc = f"a point near {roads}"
                else:
                    desc = f"({self.point.x:.0f},{self.point.y:.0f})"
            self.location_cache = f"{self.radius}m around {desc}"

        if self.estate:
            pass
        elif self.point:
            estate = cobrand.api.in_an_estate(self.point)
            self.estate = "y" if estate else "n"

    @property
    def kind_display(self):
        if self.kind == "other":
            return self.kind_other
        else:
            return self.get_kind_display()

    @property
    def location_display(self):
        return self.location_cache or self.uprn or "Unknown location"

    @property
    def point_as_latlon_string(self):
        p = self.point.transform(4326, clone=True)
        return f"{p[1]:.6f},{p[0]:.6f}"

    def get_ward_display(self):
        wards = cobrand.api.wards()
        wards = {ward["gss"]: ward["name"] for ward in wards}
        wards["outside"] = "Outside Hackney"
        return wards.get(self.ward, self.ward)

    def merge_into(self, other):
        self.merged_into = other
        MergeRecord.objects.create(mergee=self, merged_into=other, unmerge=False)

    def unmerge(self):
        MergeRecord.objects.create(
            mergee=self, merged_into=self.merged_into, unmerge=True
        )
        self.merged_into = None

    @cached_property
    def merged_into_list(self) -> list:
        """Return a list of the IDs of the Cases that this has been merged into, if any."""
        merged = Case.objects.get_merged_into_cases([self])
        return merged[self.id]

    @cached_property
    def merged_into_final(self):
        """Return the ID of the final Case that this has been merged into, if any."""
        merged = self.merged_into_list
        merged = merged[-1]["id"] if merged else None
        return merged

    @cached_property
    def timeline_merge_records(self):
        """Return a list of MergeRecords to display in the timeline for this case."""

        # Records this case and cases that are currently merged into this case
        # are referenced in.
        merge_map = self.merge_map
        direct_and_upstream_records = MergeRecord.objects.filter(
            Q(merged_into_id__in=merge_map.keys()) | Q(mergee_id__in=merge_map.keys())
        )

        # Records referencing cases that this case has merged into (possibly transitively),
        # after the time of the merge.
        downstream_records_query = Q(pk=None)  # Match nothing.
        for merged in self.merged_into_list:
            downstream_records_query |= Q(time__gte=merged["at"]) & (
                Q(merged_into_id=merged["id"]) | Q(mergee_id=merged["id"])
            )
        downstream_records = MergeRecord.objects.filter(downstream_records_query).all()

        return direct_and_upstream_records | downstream_records

    def notify_followers(self, message, triggered_by=None):
        for follower in self.followers.all():
            if follower == triggered_by or not follower.staff_web_notifications:
                continue

            Notification.objects.create(
                case=self,
                message=message,
                recipient=follower,
                triggered_by=triggered_by,
            )

    def assign(self, assignee, triggered_by=None):
        self.assigned = assignee
        self.followers.add(assignee)
        self.notify_followers(f"Assigned {assignee}.", triggered_by=triggered_by)

    def _timeline_edit_assign_entry(self, edit, prev, history_to_show):
        if history_to_show == "all":
            return {
                "action": {
                    "type": "assigned",
                    "created": edit.history_date,
                    "created_by": edit.history_user,
                    "old": prev.assigned,
                    "new": edit.assigned,
                },
                "time": edit.history_date,
            }
        else:
            return {
                "summary": "Case assigned to officer",
                "time": edit.history_date,
            }

    def _timeline_edit_entry(self, edit, changes):
        return {
            "action": {
                "created": edit.history_date,
                "created_by": edit.history_user,
                "type": "edit",
                "notes": mark_safe(
                    "<br>".join(
                        format_html(
                            "<strong>{}</strong> from {} to {}", c.field, c.old, c.new
                        )
                        for c in changes
                    )
                ),
            },
            "time": edit.history_date,
        }

    @cached_property
    def historical_entries(self):
        histories = self.history.select_related("history_user", "assigned")
        Case.objects.attach_diffs(histories)
        return histories

    def _timeline(
        self,
        actions,
        action_fn,
        complaints,
        timeline_merge_records,
        history_to_show,
        user=None,
    ):
        data = []
        for action in actions:
            row = {
                "time": action.time,
                "summary": action_fn(action),
                "action": action,
            }
            if history_to_show == "all":
                row["files"] = []
                for _file in action.files.all():
                    entry = {
                        "file": _file,
                    }
                    if user:
                        entry["can_delete"] = _file.can_delete(user)
                    row["files"].append(entry)

            if user:
                row["can_edit_action"] = action.can_edit(user)

            data.append(row)
        for complaint in complaints:
            row = {
                "complaint": complaint,
                "time": complaint.created,
            }
            data.append(row)

        for mr in timeline_merge_records:
            row = {
                "merge_record": mr,
                "time": mr.time,
            }
            data.append(row)

        edits = self.historical_entries
        if len(edits) > 1:
            edit = edits[0]
            for prev in edits[1:]:
                diff = prev._cached_diff  # Must always be available by here
                if not diff:
                    continue
                changes = []
                for d in diff.changes:
                    if d.field == "assigned":
                        data.append(
                            self._timeline_edit_assign_entry(
                                edit, prev, history_to_show
                            )
                        )
                    elif d.field == "closed":
                        continue
                    elif d.field == "merged_into":
                        continue
                    else:
                        changes.append(d)

                if changes and history_to_show == "all":
                    data.append(self._timeline_edit_entry(edit, changes))

                edit = prev

        data = sorted(data, reverse=True, key=lambda x: x["time"])
        return data

    @cached_property
    def timeline_user(self):
        """User timeline shows all manual actions, and only their own complaints"""

        def action_fn(action):
            return action.type.name

        return self._timeline(
            self.actions_public_reversed,
            action_fn,
            self.complaints_reversed,
            [],
            "assigned",
        )

    @cached_property
    def timeline_staff(self):
        """Staff timeline shows all actions and complaints on the case and its merged cases"""
        return self._timeline(
            self.actions_reversed,
            str,
            self.all_complaints_reversed,
            self.timeline_merge_records,
            "all",
        )

    def timeline_staff_with_operation_flags(self, staff):
        """Staff timeline but including flags for what operations the staff member can do"""
        return self._timeline(
            self.actions_reversed,
            str,
            self.all_complaints_reversed,
            self.timeline_merge_records,
            "all",
            user=staff,
        )

    @cached_property
    def merge_map(self):
        return Case.objects.get_merged_cases([self])

    @cached_property
    def actions_reversed(self):
        actions = self.merge_map
        query = Q(case__in=actions.keys())

        # If case A is merged into case B, case B's actions
        # after the merge are included in case A's action_reversed.
        # Note that since this is determined by the time field, an
        # action _added_ to case B after the merge but _recorded_ to have
        # happened before the merge will not be displayed.
        for merged in self.merged_into_list:
            query |= Q(time__gte=merged["at"], case=merged["id"])

        actions = Action.objects.filter(query)
        actions = actions.prefetch_related("files")
        actions = actions.order_by("-time")
        return actions

    @cached_property
    def actions_public_reversed(self):
        actions = self.actions_reversed
        actions = actions.get_public()
        return actions

    @cached_property
    def all_complainants(self):
        complaints = self.all_complaints
        return User.objects.filter(complaints__in=complaints).distinct()

    @cached_property
    def all_complaints(self):
        """The complaints on this case and any cases merged into it"""
        actions = self.merge_map
        query = Q(case__in=actions.keys())
        complaints = Complaint.objects.filter(query).select_related("complainant")
        return complaints

    @cached_property
    def complaints_reversed(self):
        complaints = self.complaints
        complaints = complaints.order_by("-created")
        return complaints

    @cached_property
    def all_complaints_reversed(self):
        complaints = self.all_complaints
        complaints = complaints.order_by("-created")
        return list(complaints)

    @property
    def last_update(self):
        for event in self.timeline_staff:
            return event
        return None

    @property
    def had_abatement_notice(self):
        for action in self.actions_reversed:
            if (
                action.type_id
                and action.type.name == "Abatement Notice “Section 80” served"
            ):
                return True
        return False

    @cached_property
    def number_all_complaints(self):
        return len(self.all_complaints_reversed)

    @cached_property
    def number_all_complainants(self):
        return len({c.complainant_id for c in self.all_complaints_reversed})

    @cached_property
    def reoccurrences(self):
        return max(self.number_all_complaints - self.number_all_complainants, 0)

    @property
    def file_storage_used_bytes(self):
        bytes_used = 0
        for action in self.actions.prefetch_related("files").all():
            for af in action.files.all():
                bytes_used += af.file.size
        return bytes_used

    @property
    def file_storage_remaining_bytes(self):
        return math.floor(
            (CaseSettingsSingleton.instance.max_file_storage_mb * 1000 * 1000)
            - self.file_storage_used_bytes
        )


class Complaint(AbstractModel):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="complaints")
    complainant = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="complaints",
    )

    happening_now = models.BooleanField()
    start = models.DateTimeField(default=timezone.now)
    end = models.DateTimeField(default=timezone.now)
    rooms = models.TextField(blank=True)
    description = models.TextField(blank=True)
    effect = models.TextField(blank=True)


class ActionType(models.Model):
    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("staff", "Staff"),
        ("internal", "Internal"),
    ]

    name = models.CharField(max_length=100)
    common = models.BooleanField(default=False)
    visibility = models.CharField(
        max_length=10, choices=VISIBILITY_CHOICES, default="staff"
    )

    @classproperty
    def case_closed(cls):
        typ, _ = ActionType.objects.get_or_create(
            name="Case closed", defaults={"visibility": "staff"}
        )
        return typ

    @classproperty
    def case_reopened(cls):
        typ, _ = ActionType.objects.get_or_create(
            name="Case reopened", defaults={"visibility": "staff"}
        )
        return typ

    @classproperty
    def edit_case(cls):
        typ, _ = ActionType.objects.get_or_create(
            name="Edit case", defaults={"visibility": "internal"}
        )
        return typ

    @classproperty
    def visit(cls):
        typ, _ = ActionType.objects.get_or_create(
            name="Visit", defaults={"visibility": "staff"}
        )
        return typ

    def __str__(self):
        return self.name


class ActionQuerySet(models.QuerySet):
    def get_public(self):
        return self.filter(type__visibility="public")


class ActionManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related("created_by", "case", "type")
        return qs


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
    notes_last_edit_time = models.DateTimeField(blank=True, null=True)
    time = models.DateTimeField(default=timezone.now)

    objects = ActionManager.from_queryset(ActionQuerySet)()

    def can_edit(self, user):
        return (
            user == self.created_by
            and timezone.now() - self.created
            <= CaseSettingsSingleton.instance.logged_action_editing_window
        )

    def __str__(self):
        if self.type:
            return f"{self.created_by}, {self.type.name}, case {self.case_id}"
        else:
            return f"{self.created_by}, case {self.case_id}, unknown action"


class ActionFile(AbstractModel):
    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="files")
    file = models.FileField()
    original_name = models.CharField(max_length=128)

    @property
    def human_readable_size(self):
        return naturalsize(self.file.size)

    def can_delete(self, user):
        return user == self.created_by

    def get_absolute_url(self):
        return reverse(
            "action-file", args=[self.action.case.pk, self.action.pk, self.pk]
        )


class MergeRecord(AbstractModel):
    mergee = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name="merge_records"
    )
    merged_into = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name="mergee_records"
    )
    unmerge = models.BooleanField(default=False)
    time = models.DateTimeField(default=timezone.now)


class Notification(AbstractModel):
    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name="notifications"
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="notifications_triggered",
        blank=True,
        null=True,
    )
    time = models.DateTimeField(default=timezone.now)
    message = models.TextField()
    read = models.BooleanField(default=False)
