import datetime

# from django.core.exceptions import ValidationError
from crispy_forms_gds.fields import DateInputField
from django import forms

from noiseworks.forms import GDSForm
from noiseworks.forms import StepForm

from .widgets import TimeWidget


def coerce_to_date(d):
    if d == "today":
        return datetime.date.today()
    else:  # "yesterday"
        return datetime.date.today() - datetime.timedelta(days=1)


class IsItHappeningNowForm(StepForm):
    happening_now = forms.TypedChoiceField(
        choices=((1, "Yes"), (0, "No")),
        widget=forms.RadioSelect,
        coerce=int,
        label="Is the noise happening right now?",
    )


class HappeningNowForm(StepForm):
    start_date = forms.TypedChoiceField(
        choices=(("today", "Today"), ("yesterday", "Yesterday")),
        widget=forms.RadioSelect,
        label="When did today’s noise start?",
        coerce=coerce_to_date,
    )
    start_time = forms.TimeField(
        help_text="For example, 9pm or 2:30am – enter 12am for midnight",
        widget=TimeWidget,
    )


class NotHappeningNowForm(StepForm):
    start_date = DateInputField(require_all_fields=False)
    start_time = forms.TimeField(
        help_text="For example, 9pm or 2:30am – enter 12am for midnight",
        widget=TimeWidget,
    )
    end_time = forms.TimeField(
        help_text="For example, 10pm or 3:30am – enter 12pm for midday",
        widget=TimeWidget,
    )


class RoomsAffectedForm(StepForm):
    title = "Details of the noise"
    rooms = forms.CharField(
        widget=forms.Textarea, label="Which rooms in your property are affected?"
    )


class DescribeNoiseForm(StepForm):
    title = "Details of the noise"
    description = forms.CharField(
        widget=forms.Textarea,
        label="Can you describe the noise?",
        help_text="Please include as much detail as possible e.g. if the Noise is about a car alarm include the car’s colour, car registration etc",
    )


class EffectForm(StepForm):
    title = "Details of the noise"
    effect = forms.CharField(
        widget=forms.Textarea, label="What effect has the noise had on you?"
    )


class InternalFlagsForm(StepForm):
    title = "Internal Flags"
    priority = forms.BooleanField(label="This case is a priority", required=False)
    has_review_date = forms.BooleanField(
        label="This case has a review date", required=False
    )
    review_date = DateInputField(label="", required=False)


class SummaryForm(StepForm):
    submit_text = "Submit"
    title = "Check your answers"
    template = "cases/add/summary.html"  # Not used by recurrence
    true_statement = forms.BooleanField(
        label="This statement is true to the best of my knowledge and belief and I make it knowing that, if it is tendered in evidence, I shall be liable to prosecution if I have wilfully stated in it anything which I know to be false or do not believe to be true."
    )
