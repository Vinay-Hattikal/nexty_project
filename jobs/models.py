# jobs/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
import os

def resume_pdf_upload_path(instance, filename):
    return os.path.join('resumes', filename)

class Resume(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resumes')
    title = models.CharField(max_length=255, default='My Resume')
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    pdf_file = models.FileField(upload_to=resume_pdf_upload_path, null=True, blank=True)

    def __str__(self):
        return f"{self.owner.username} - {self.title}"


class Job(models.Model):
    hr = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posted_jobs')
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    is_remote = models.BooleanField(default=False)
    salary = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    required_skills = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} @ {self.company or '—'}"

    def is_open(self):
        if not self.is_active:
            return False
        if self.expiry_date and self.expiry_date < timezone.now().date():
            return False
        return True


APPLICATION_STATUS = (
    ('applied', 'Applied'),
    ('shortlisted', 'Shortlisted'),
    ('rejected', 'Rejected'),
    ('interview_scheduled', 'Interview Scheduled'),
)

def application_resume_upload_path(instance, filename):
    return os.path.join('applications', str(instance.student.id), filename)

class Application(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='applications')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    resume = models.ForeignKey(Resume, null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_resume = models.FileField(upload_to=application_resume_upload_path, null=True, blank=True)
    cover_letter = models.TextField(blank=True)
    ats_score = models.FloatField(null=True, blank=True)
    missing_keywords = models.JSONField(default=list, blank=True)
    matched_keywords = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=32, choices=APPLICATION_STATUS, default='applied')
    applied_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.student.username} -> {self.job.title} ({self.status})"
