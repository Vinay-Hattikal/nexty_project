# interview/models.py
from django.db import models

CATEGORY_CHOICES = [
    ('important', 'Important'),
    ('pyq', 'Python Questions'),
    ('sys', 'System Design'),
    # add your categories...
]

class InterviewQuestion(models.Model):
    role = models.CharField(max_length=120, db_index=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='important', db_index=True)
    question = models.TextField()
    answer = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text='comma-separated tags')
    source = models.CharField(max_length=255, blank=True)
    difficulty = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role} - {self.question[:80]}"

    def tag_list(self):
        if not self.tags:
            return []
        return [t.strip().lower() for t in self.tags.split(',') if t.strip()]

    def save(self, *args, **kwargs):
        # normalize tags (lowercase, no extra spaces)
        if self.tags:
            tags = [t.strip().lower() for t in self.tags.split(',') if t.strip()]
            self.tags = ','.join(tags)
        super().save(*args, **kwargs)
