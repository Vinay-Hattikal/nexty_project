# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_STUDENT = 'student'
    ROLE_HR = 'hr'
    ROLE_CHOICES = [
        (ROLE_STUDENT, 'Student'),
        (ROLE_HR, 'HR'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)

    def is_student(self):
        return self.role == self.ROLE_STUDENT

    def is_hr(self):
        return self.role == self.ROLE_HR
