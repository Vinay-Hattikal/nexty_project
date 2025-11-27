# accounts/urls.py
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('dashboard/hr/', views.hr_dashboard, name='hr_dashboard'),
    path('profile/', views.profile_view, name='profile'),  # you must implement profile_view
]
