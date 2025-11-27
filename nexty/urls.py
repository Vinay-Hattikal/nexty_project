# nexty/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from jobs import views as job_views

# import views
from accounts import views as account_views
from jobs import views as jobs_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth (login/logout/password reset)
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/signup/', account_views.signup, name='signup'),
    path('accounts/dashboard-redirect/', account_views.dashboard_redirect, name='dashboard-redirect'),
    path('accounts/dashboard/student/', account_views.student_dashboard, name='student_dashboard'),
    path('accounts/dashboard/hr/', account_views.hr_dashboard, name='hr_dashboard'),
    path('prep/', include('interview.urls', namespace='interview')),


    # Home
    path('', TemplateView.as_view(template_name='home.html'), name='home'),

    # Resume builder & API
    path('jobs/resumes/', jobs_views.resume_list, name='resume_list'),
    path('jobs/resume/create/', jobs_views.create_or_edit_resume_page, name='create_resume'),
    path('jobs/resume/edit/<int:resume_id>/', jobs_views.create_or_edit_resume_page, name='edit_resume'),
    path('jobs/api/resume/<int:resume_id>/', jobs_views.get_resume_api, name='get_resume_api'),
    path('jobs/resume/save/', jobs_views.save_resume_api, name='save_resume_api'),
    path('jobs/resume/<int:resume_id>/', jobs_views.resume_detail, name='resume_detail'),
    path('jobs/resume/<int:resume_id>/preview/', jobs_views.resume_preview, name='resume_preview'),
    path('jobs/resume/<int:resume_id>/download/', jobs_views.resume_download_pdf, name='resume_download'),
    path('prep/', include('interview.urls', namespace='interview')),


    # Job posting / browsing (Phase 3)
    # Student-facing
    path('jobs/', jobs_views.job_list, name='job_list'),

    # Apply flow (Phase 4) - place before the generic job_detail route
    path('jobs/<int:job_id>/apply/', jobs_views.apply_start, name='job_apply'),
    path('jobs/<int:job_id>/', jobs_views.job_detail, name='job_detail'),

    # HR-facing job management
    path('hr/jobs/create/', jobs_views.job_create, name='job_create'),
    path('hr/jobs/edit/<int:job_id>/', jobs_views.job_edit, name='job_edit'),
    path('hr/jobs/delete/<int:job_id>/', jobs_views.job_delete, name='job_delete'),
    path('hr/job/<int:job_id>/applications/', jobs_views.hr_applications_for_job, name='hr_applications_for_job'),
    path('hr/application/<int:app_id>/', jobs_views.hr_application_detail, name='hr_application_detail'),

    # Applications / user pages
    path('applications/my/', jobs_views.student_applications, name='student_applications'),
]

# Serve media in development (only when DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
