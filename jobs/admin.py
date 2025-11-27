from django.contrib import admin
from .models import Resume, Job
from .models import Resume, Job, Application


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'updated_at')

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'hr', 'created_at', 'expiry_date', 'is_active')
    list_filter = ('is_active', 'is_remote', 'company')
    search_fields = ('title', 'company', 'description')

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('student', 'job', 'status', 'ats_score', 'applied_at')
    list_filter = ('status',)
    search_fields = ('student__username', 'job__title')