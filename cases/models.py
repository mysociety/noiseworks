import requests
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html, mark_safe
from simple_history.models import HistoricalRecords

from accounts.models import User
from noiseworks import cobrand


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


class CaseManager(models.Manager):
    def unmerged(self):
        q = Q(merge_action__isnull=True)
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

        merge_map = Action.objects.get_merged_cases(qs)
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
                prev._cached_diff = edit.diff_against(prev)
                edit = prev

    def get_merged_into_cases(self, cases):
        """Given a list of Case IDs, returns a dict mapping those Cases into
        ones they have been merged into."""
        case_ids = map(lambda x: str(x.id), cases)
        case_ids = ",".join(case_ids)
        if not case_ids:
            return {}
        query = Action.objects.raw(
            """WITH RECURSIVE cte AS (
                SELECT s.id,s.created,s.case_old_id,s.case_id FROM cases_action s WHERE s.case_old_id IN (%s)
                UNION
                SELECT s.id,s.created,cte.case_old_id,s.case_id FROM cte JOIN cases_action s ON cte.case_id = s.case_old_id
            )
            SELECT * FROM cte """
            % case_ids,
        )

        merge_map = {c.id: [] for c in cases}
        for action in query:
            # Even though merging actions should not have an edited 'time', we need to
            # use 'time' rather than 'created' for the merged 'at'.
            # This is because in other action queries we use 'time' and we should be consistent,
            # especially as there is a small delta between the values of 'time' and 'created' for
            # a newly created action.
            merge_map[action.case_old_id].append(
                {"id": action.case_id, "at": action.time}
            )
        return merge_map


class Case(AbstractModel):
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

    perpetrators = models.ManyToManyField(User, related_name="cases_perpetrated")

    assigned = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="assignations",
    )
    followers = models.ManyToManyField(User, related_name="cases_following")

    history = HistoricalRecords(excluded_fields=["modified", "modified_by"])
    objects = CaseManager()

    class Meta:
        ordering = ("-modified", "-id")

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
            return
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
        Action.objects.create(case_old=self, case=other)

    @cached_property
    def merged_into_list(self) -> list:
        """Return a list of the IDs of the Cases that this has been merged into, if any."""
        merged = Case.objects.get_merged_into_cases([self])
        return merged[self.id]

    @cached_property
    def merged_into(self):
        """Return the ID of the final Case that this has been merged into, if any."""
        merged = self.merged_into_list
        merged = merged[-1]["id"] if merged else None
        return merged

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

    def _timeline(self, actions, action_fn, complaints, history_to_show):
        data = []
        for action in actions:
            row = {
                "time": action.time,
                "summary": action_fn(action),
                "action": action,
            }
            data.append(row)
        for complaint in complaints:
            row = {
                "complaint": complaint,
                "time": complaint.created,
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
            "assigned",
        )

    @cached_property
    def timeline_staff(self):
        """Staff timeline shows all actions and complaints on the case and its merged cases"""
        return self._timeline(
            self.actions_reversed, str, self.all_complaints_reversed, "all"
        )

    @cached_property
    def action_merge_map(self):
        return Action.objects.get_merged_cases([self])

    @cached_property
    def actions_reversed(self):
        actions = self.action_merge_map
        query = Q(case__in=actions.keys())

        # If case A is merged into case B, case B's actions
        # after the merge are included in case A's action_reversed.
        # Note that since this is determined by the time field, an
        # action _added_ to case B after the merge but _recorded_ to have
        # happened before the merge will not be displayed.
        for merged in self.merged_into_list:
            query |= Q(time__gte=merged["at"], case=merged["id"])

        actions = Action.objects.filter(query)
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
        actions = self.action_merge_map
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

    def __str__(self):
        return self.name


class ActionQuerySet(models.QuerySet):
    def get_public(self):
        return self.filter(type__visibility="public")


class ActionManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related("created_by", "case", "type", "case_old")
        return qs

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
    time = models.DateTimeField(default=timezone.now)

    # Merge
    case_old = models.ForeignKey(
        Case,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="merge_action",
    )

    objects = ActionManager.from_queryset(ActionQuerySet)()

    def __str__(self):
        if self.case_old:
            return f"{self.created_by} merged case {self.case_old_id} into case {self.case_id}"
        elif self.type:
            return f"{self.created_by}, {self.type.name}, case {self.case_id}"
        else:
            return f"{self.created_by}, case {self.case_id}, unknown action"
