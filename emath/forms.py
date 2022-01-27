from django import forms

from .models import Problem


class ProblemForm(forms.Form):

    ans = forms.ChoiceField(
        required = True,
        choices = (),
        widget=forms.RadioSelect
    )

    def __init__(self, ans_choices, *args, **kwargs):
        super(ProblemForm, self).__init__(*args, **kwargs)
        self.fields['ans'].choices = ans_choices
