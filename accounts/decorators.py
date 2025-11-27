from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from functools import wraps

def hr_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not getattr(request.user, 'role', None) == 'hr':
            raise PermissionDenied("HR access required.")
        return view_func(request, *args, **kwargs)
    return _wrapped
