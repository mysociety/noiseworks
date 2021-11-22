import datetime
from django import forms

# from django.core.exceptions import ValidationError
from crispy_forms_gds.fields import DateInputField
from noiseworks.forms import GDSForm


class StepForm(GDSForm, forms.Form):
    submit_text = "Next"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_tag = False


class TimeWidget(forms.TextInput):
    pass


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
        widget=forms.Textarea, label="Can you describe the noise?"
    )


class EffectForm(StepForm):
    title = "Details of the noise"
    effect = forms.CharField(
        widget=forms.Textarea, label="What effect has the noise had on you?"
    )


class SummaryForm(StepForm):
    submit_text = "Submit"
    title = "Check your answers"

    true_statement = forms.BooleanField(
        label="This statement is true to the best of my knowledge and belief and I make it knowing that, if it is tendered in evidence, I shall be liable to prosecution if I have wilfully stated in it anything which I know to be false or do not believe to be true."
    )
