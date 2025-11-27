# jobs/forms.py
from django import forms
from .models import Job
from django.core.exceptions import ValidationError
import datetime

class JobForm(forms.ModelForm):
    # Allow a comma-separated skills field shown to user
    skills_csv = forms.CharField(required=False, help_text="Comma separated skills (e.g. Python,SQL,Django)")

    class Meta:
        model = Job
        fields = ['title', 'company', 'location', 'is_remote', 'salary', 'description', 'expiry_date', 'is_active']

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        instance = kwargs.get('instance')
        if instance and instance.required_skills:
            initial['skills_csv'] = ', '.join(instance.required_skills)
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def clean_expiry_date(self):
        d = self.cleaned_data.get('expiry_date')
        if d and d < datetime.date.today():
            raise ValidationError("Expiry date cannot be in the past.")
        return d

    def clean(self):
        cleaned = super().clean()
        skills_csv = cleaned.get('skills_csv', '')
        cleaned['required_skills'] = [s.strip() for s in skills_csv.split(',') if s.strip()]
        return cleaned

    def save(self, commit=True):
        job = super().save(commit=False)
        job.required_skills = self.cleaned_data.get('required_skills', [])
        if commit:
            job.save()
        return job


class ApplyChooseForm(forms.Form):
    """
    Student can either choose a built resume (resume_id) OR upload a resume file.
    Server-side validation enforces XOR (exactly one provided).
    Note: resume_id is accepted as a string here (from radio input) and converted to int if present.
    """
    resume_id = forms.CharField(required=False)   # accept as text and convert in clean()
    uploaded_resume = forms.FileField(required=False)
    cover_letter = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows':4}), max_length=2000)

    def clean_uploaded_resume(self):
        f = self.cleaned_data.get('uploaded_resume')
        if not f:
            return f
        name = f.name.lower()
        if not (name.endswith('.pdf') or name.endswith('.docx')):
            raise forms.ValidationError("Only PDF and DOCX files are allowed.")
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("File size must be <= 5 MB.")
        return f

    def clean(self):
        cleaned = super().clean()
        resume_id_raw = cleaned.get('resume_id')
        uploaded = cleaned.get('uploaded_resume')

        # Normalize resume_id: empty string -> None
        if resume_id_raw in (None, '', 'None'):
            resume_id = None
        else:
            # try convert to int
            try:
                resume_id = int(resume_id_raw)
            except (ValueError, TypeError):
                # invalid id supplied
                raise ValidationError("Selected resume id is invalid.")
        # XOR rule: exactly one of resume_id OR uploaded_resume must be provided.
        if (bool(resume_id) and bool(uploaded)) or (not bool(resume_id) and not bool(uploaded)):
            raise ValidationError("Please provide exactly one resume option: choose a saved resume OR upload a file (not both).")

        cleaned['resume_id'] = resume_id
        return cleaned


class ShortlistForm(forms.Form):
    interview_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    interview_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    timezone = forms.CharField(required=False, help_text="Optional timezone (e.g. UTC, Asia/Kolkata)")
    am_pm = forms.ChoiceField(required=False, choices=(('AM','AM'),('PM','PM')), help_text="Optional (if you prefer AM/PM)")
    message = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows':4}), max_length=1000)
    meeting_link = forms.URLField(required=False, help_text="Virtual meeting URL (Zoom/Meet/Teams)")
