# interview/utils.py
import os
from io import BytesIO
from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from xhtml2pdf import pisa

def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those
    resources (static and media files).
    """
    # absolute URL (http/https) - return unchanged
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri

    # handle media files
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    elif uri.startswith(settings.STATIC_URL):
        # use Django staticfiles finders
        path = finders.find(uri.replace(settings.STATIC_URL, ""))
        # finders.find may return list
        if isinstance(path, (list, tuple)):
            path = path[0]
    else:
        # try relative path
        path = finders.find(uri) or uri

    # final check
    if not os.path.isfile(path):
        # If file doesn't exist, return original URI (pisa will try to fetch)
        return uri
    return path

def render_to_pdf(template_src, context_dict=None):
    """
    Render a Django template to PDF and return bytes (or None on error).
    Uses xhtml2pdf (pisa). Provide link_callback to resolve static/media files.
    """
    context_dict = context_dict or {}
    html = render_to_string(template_src, context_dict)
    result = BytesIO()
    # CreatePDF can accept a file-like for src; supply HTML bytes and dest buffer
    pdf = pisa.CreatePDF(BytesIO(html.encode('utf-8')), dest=result, link_callback=link_callback)
    if pdf.err:
        # None indicates failure
        return None
    return result.getvalue()
