# jobs/urls.py
from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    # job listing / detail
    path('', views.job_list, name='job_list'),                     # /jobs/
    path('<int:job_id>/', views.job_detail, name='job_detail'),    # /jobs/123/

    # job CRUD for HR
    path('post/', views.job_create, name='job_create'),            # /jobs/post/
    path('<int:job_id>/edit/', views.job_edit, name='job_edit'),   # /jobs/123/edit/
    path('<int:job_id>/delete/', views.job_delete, name='job_delete'), # /jobs/123/delete/

    # application flow
    path('<int:job_id>/apply/', views.apply_start, name='job_apply'),  # /jobs/123/apply/

    # HR applications view
    path('<int:job_id>/applications/', views.hr_applications_for_job, name='hr_applications_for_job'),

    # preview/download resume endpoints (if you want them inside jobs)
    path('resume/', views.resume_list, name='resume_list'),        # optional: /jobs/resume/
]
