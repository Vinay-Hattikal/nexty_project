# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.db.models import Prefetch
from .forms import UserSignupForm
from jobs.models import Job, Application


def signup(request):
    if request.method == 'POST':
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # auto-login after signup
            login(request, user)
            return redirect('dashboard-redirect')
    else:
        form = UserSignupForm()
    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def dashboard_redirect(request):
    if request.user.is_student():
        return redirect('student_dashboard')
    return redirect('hr_dashboard')


@login_required
def student_dashboard(request):
    return render(request, 'accounts/student_dashboard.html')


@login_required
def hr_dashboard(request):
    """
    HR dashboard: show all jobs posted by the HR and link to applications.
    """
    user = request.user
    if not getattr(user, "is_hr", lambda: False)():
        return HttpResponseForbidden("HR access required.")

    jobs = Job.objects.filter(hr=user).prefetch_related(
        Prefetch("applications", queryset=Application.objects.select_related("student", "resume"))
    ).order_by("-created_at")

    return render(request, "accounts/hr_dashboard.html", {"jobs": jobs})
