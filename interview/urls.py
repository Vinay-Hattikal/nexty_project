# interview/urls.py
from django.urls import path
from . import views

app_name = 'interview'

urlpatterns = [
    path('', views.index, name='index'),
    path('question/<int:pk>/', views.question_detail, name='question_detail'),
    path('api/search/', views.api_search, name='api_search'),
    path('question/<int:pk>/pdf/', views.question_pdf, name='question_pdf'),  # new PDF endpoint
]
