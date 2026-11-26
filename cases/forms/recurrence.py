import datetime

# from django.core.exceptions import ValidationError
from crispy_forms_gds.fields import DateInputField
from django import forms

from cobrands.registry import get_cobrand
from noiseworks.forms import GDSForm, StepForm

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
        label="Is the issue happening right now?",
    )


class HappeningNowForm(StepForm):
    start_date = forms.TypedChoiceField(
        choices=(("today", "Today"), ("yesterday", "Yesterday")),
        widget=forms.RadioSelect,
        label="When did today’s problem start?",
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


class DetailForms(StepForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = self.form_label_lookup(kwargs, "Details of the issue", "details")


class RoomsAffectedForm(DetailForms):
    rooms = forms.CharField(
        widget=forms.Textarea, label="Which rooms in your property are affected?"
    )


class DescribeForm(DetailForms):
    description = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        desc = self.fields["description"]
        desc.label = self.form_label_lookup(kwargs, "Can you describe the problem?")
        desc.help_text = self.form_label_lookup(
            kwargs, "Please include as much detail as possible", "describe_help"
        )


class EffectForm(DetailForms):
    effect = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        effect = self.fields["effect"]
        effect.label = self.form_label_lookup(
            kwargs, "What effect has the issue had on you?"
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
