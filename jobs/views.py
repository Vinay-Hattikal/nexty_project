# jobs/views.py
import json
import os
import re
import logging
import shutil
from io import BytesIO
from functools import wraps
from datetime import datetime
from django.conf import settings

from django.template.loader import render_to_string, get_template
from django.contrib.staticfiles import finders
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone

from .forms import ApplyChooseForm, JobForm, ShortlistForm
from .models import Resume, Job, Application
from .utils import extract_text, resume_json_to_text, compute_ats_score

logger = logging.getLogger(__name__)

# HR decorator (try to import project decorator, fallback to simple check)
try:
    from accounts.decorators import hr_required
except Exception:
    def hr_required(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if getattr(request.user, 'role', None) != 'hr' and not getattr(request.user, 'is_staff', False):
                return HttpResponseForbidden("HR access required.")
            return view_func(request, *args, **kwargs)
        return _wrapped


# -------------------------
# Resume endpoints
# -------------------------
@login_required
def resume_list(request):
    resumes = Resume.objects.filter(owner=request.user).order_by('-updated_at')
    return render(request, 'jobs/resume_list.html', {'resumes': resumes})


@login_required
def create_or_edit_resume_page(request, resume_id=None):
    return render(request, 'jobs/create_resume.html', {})


@login_required
def get_resume_api(request, resume_id):
    resume = get_object_or_404(Resume, id=resume_id)
    if resume.owner != request.user:
        return HttpResponseForbidden("Not allowed")
    return JsonResponse({'id': resume.id, 'title': resume.title, 'data': resume.data or {}})


def _clear_resume_cache(resume):
    try:
        media_subdir = os.path.join(settings.MEDIA_ROOT, 'resumes')
        prefix = f"{resume.owner.username}_r{resume.id}_"
        if os.path.isdir(media_subdir):
            for f in os.listdir(media_subdir):
                if f.startswith(prefix):
                    path = os.path.join(media_subdir, f)
                    try:
                        os.remove(path)
                        logger.info("Removed cached resume PDF: %s", path)
                    except Exception as e:
                        logger.debug("Failed to remove cached file %s: %s", path, e)
    except Exception as e:
        logger.debug("Error clearing resume cache: %s", e)


@login_required
@require_http_methods(["POST"])
def save_resume_api(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    title = payload.get('title', 'My Resume')
    data = payload.get('data', {})
    resume_id = payload.get('resume_id')

    if resume_id:
        try:
            resume = Resume.objects.get(id=resume_id, owner=request.user)
        except Resume.DoesNotExist:
            return HttpResponseForbidden("No such resume or no permission.")
        _clear_resume_cache(resume)
        resume.title = title
        resume.data = data
        try:
            resume.updated_at = timezone.now()
        except Exception:
            pass
        resume.save()
        _clear_resume_cache(resume)
        logger.info("Resume %s saved by %s", resume.id, request.user.username)
    else:
        resume = Resume.objects.create(owner=request.user, title=title, data=data)
        logger.info("New resume %s created by %s", resume.id, request.user.username)

    return JsonResponse({'ok': True, 'resume_id': resume.id})


@login_required
def resume_detail(request, resume_id):
    resume = get_object_or_404(Resume, id=resume_id)
    if resume.owner != request.user and not (getattr(request.user, 'role', None) == 'hr' or getattr(request.user, 'is_staff', False)):
        return HttpResponseForbidden("Not allowed")
    return render(request, 'jobs/resume_detail.html', {'resume': resume})


# -------------------------
# Preview & download helpers
# -------------------------
# Use fragment templates (no html/head/body, no extends) inside templates/jobs/includes/
TEMPLATE_MAP = {
    'modern': 'jobs/includes/resume_modern_inner.html',
    'classic': 'jobs/includes/resume_classic_inner.html',
    'minimal': 'jobs/includes/resume_minimal_inner.html',
}


@login_required
def resume_preview(request, resume_id, template_key='modern'):
    resume = get_object_or_404(Resume, id=resume_id)
    if resume.owner != request.user and not (getattr(request.user, 'role', None) == 'hr' or getattr(request.user, 'is_staff', False)):
        return HttpResponseForbidden("Not allowed")
    template_file = TEMPLATE_MAP.get(template_key, TEMPLATE_MAP['modern'])
    context = {'resume': resume, 'template_key': template_key, 'template': template_file}
    return render(request, 'jobs/resume_template_preview.html', context)


def _link_callback(uri, rel, request=None):
    # Map static/media URIs to filesystem paths for xhtml2pdf/pisa
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri

    static_url = getattr(settings, 'STATIC_URL', '/static/')
    media_url = getattr(settings, 'MEDIA_URL', '/media/')

    if static_url and uri.startswith(static_url):
        relpath = uri.replace(static_url, '').lstrip('/')
        candidates = []
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if static_root:
            candidates.append(os.path.join(static_root, relpath))
        candidates.append(os.path.join(settings.BASE_DIR, 'static', relpath))
        for c in candidates:
            if os.path.exists(c):
                return c
        return uri

    if media_url and uri.startswith(media_url):
        relpath = uri.replace(media_url, '').lstrip('/')
        candidate = os.path.join(settings.MEDIA_ROOT, relpath)
        if os.path.exists(candidate):
            return candidate
        return uri

    return uri


# CSS sanitizer to make xhtml2pdf happier (removes constructs pisa can't parse)
def _sanitize_css_for_pisa(css_text: str) -> str:
    """
    Sanitize CSS so xhtml2pdf (pisa) can parse it:
    - Remove comments, @media/@supports/@keyframes blocks, pseudo-elements, content declarations, css variables, gradients, url(), calc(), var(), etc.
    - Finally, remove any leftover unmatched '{' or '}' fragments to avoid parser errors.
    """
    if not css_text:
        return ''

    txt = css_text

    # Normalize line endings
    txt = txt.replace('\r\n', '\n').replace('\r', '\n')

    # Remove comments
    txt = re.sub(r'/\*[\s\S]*?\*/', '', txt)

    # Remove @-rules that often confuse pisa (media/supports/keyframes)
    txt = re.sub(r'@media[^{]*\{(?:[^{}]|\{[^}]*\})*\}', '', txt, flags=re.IGNORECASE)
    txt = re.sub(r'@supports[^{]*\{(?:[^{}]|\{[^}]*\})*\}', '', txt, flags=re.IGNORECASE)
    txt = re.sub(r'@keyframes[^{]*\{(?:[^{}]|\{[^}]*\})*\}', '', txt, flags=re.IGNORECASE)

    # Remove pseudo-elements (::before, ::after) rules entirely
    txt = re.sub(r'([^{;]+)::?(?:before|after)[^{]*\{[^}]*\}', '', txt, flags=re.IGNORECASE)

    # Remove content declarations (these often include quotes / counters)
    txt = re.sub(r'content\s*:\s*([^;}]*)[;}]', '}', txt, flags=re.IGNORECASE)

    # Remove CSS variables & var() usage (pisa doesn't support them)
    txt = re.sub(r'--[\w-]+\s*:\s*[^;{}]*;', '', txt)
    txt = re.sub(r'var\([^)]*\)', '', txt)

    # Remove complex backgrounds / gradients / url(...) usages
    txt = re.sub(r'background(?:-[\w]+)?\s*:[^;{}]*;', '', txt, flags=re.IGNORECASE)
    txt = re.sub(r'(?:linear|radial|conic)-gradient\([^)]*\)', '', txt, flags=re.IGNORECASE)
    txt = re.sub(r'url\([^)]*\)', '', txt, flags=re.IGNORECASE)

    # Remove calc/min/max/clamp/env(...) usages
    txt = re.sub(r'(calc|min|max|clamp|env)\([^)]*\)', '', txt, flags=re.IGNORECASE)

    # Remove stray backslash unicode escapes left over
    txt = re.sub(r'\\[0-9a-fA-F]{1,6}\s?', '', txt)

    # Remove vendor-specific properties that may confuse parser (best-effort)
    txt = re.sub(r'-webkit-[\w-]+\s*:[^;{}]*;', '', txt, flags=re.IGNORECASE)
    txt = re.sub(r'-moz-[\w-]+\s*:[^;{}]*;', '', txt, flags=re.IGNORECASE)

    # Collapse empty rules and multiple blank lines
    txt = re.sub(r'[ \t]*\{[ \t]*\}', '', txt)
    txt = re.sub(r'\n\s*\n+', '\n', txt)

    # Remove stray '.' characters that may appear immediately before selectors
    txt = re.sub(r'\.\s*(?=[\w\.\#\-\:\[]+[\s\S]*\{)', '', txt)

    # Remove accidental characters left at end of declarations like ";\n." -> ";\n"
    txt = re.sub(r';\s*\.\s*', ';', txt)

    # BEST-EFFORT: Insert missing closing '}' before the next selector if a rule was left unterminated.
    txt = re.sub(r'(\{[^}]*?)(?=\s*[A-Za-z0-9\.\#\:\[\-_*][^{]*\{)', r'\1}', txt, flags=re.S)

    # If there are still unmatched '{' at EOF, append closing braces to balance.
    opens = txt.count('{')
    closes = txt.count('}')
    if opens > closes:
        txt = txt + ('}' * (opens - closes))

    # Final tidy: remove whitespace-only lines and trailing spaces
    txt = re.sub(r'[ \t]+\n', '\n', txt)
    txt = re.sub(r'\n\s+\}', '\n}', txt)
    txt = re.sub(r'\n{2,}', '\n', txt)

    return txt.strip()


def _normalize_html_for_pdf(fragment_html: str, include_css: bool = True) -> str:
    """
    Accept a fragment (may contain <style> blocks at top) and return a single
    scaffolded HTML document safe for PDF generators.
    If include_css is False, any <style> blocks in the fragment are stripped.
    """
    if not fragment_html:
        return fragment_html

    # Collect all <style> content (if include_css True)
    styles = []
    if include_css:
        for m in re.finditer(r'(<style[^>]*>)([\s\S]*?)(</style>)', fragment_html, flags=re.IGNORECASE):
            styles.append(m.group(2) or '')

    # Remove existing html/head/body tags if any (we expect fragments)
    body_inner = re.sub(r'</?(?:html|head|body)[^>]*>', '', fragment_html, flags=re.IGNORECASE)

    if not include_css:
        # strip any style blocks entirely from body_inner
        body_inner = re.sub(r'<style[\s\S]*?</style>', '', body_inner, flags=re.IGNORECASE)

    combined_css = "\n\n".join(styles).strip()
    sanitized_css = _sanitize_css_for_pisa(combined_css) if combined_css else ''

    scaffold = "<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
    if sanitized_css:
        scaffold += "<style>\n" + sanitized_css + "\n</style>\n"
    scaffold += "</head>\n<body>\n" + body_inner + "\n</body>\n</html>\n"
    return scaffold


def _get_template_mtime(template_name: str) -> float:
    """
    Try to resolve a Django template name to a filesystem path and return its mtime.
    Falls back to checking templates/<template_name> under BASE_DIR and TEMPLATES DIRS.
    Returns 0.0 if not resolvable.
    """
    try:
        tpl = get_template(template_name)
        origin = getattr(tpl, 'origin', None)
        if origin and getattr(origin, 'name', None) and os.path.exists(origin.name):
            return float(os.path.getmtime(origin.name))
    except Exception:
        pass

    try:
        candidate = os.path.join(settings.BASE_DIR, 'templates', template_name)
        if os.path.exists(candidate):
            return float(os.path.getmtime(candidate))
    except Exception:
        pass

    try:
        tpl_dirs = []
        for origin_entry in getattr(settings, 'TEMPLATES', []):
            dirs = origin_entry.get('DIRS', [])
            if dirs:
                tpl_dirs.extend(dirs)
        for d in tpl_dirs:
            candidate = os.path.join(d, template_name)
            if os.path.exists(candidate):
                return float(os.path.getmtime(candidate))
    except Exception:
        pass

    return 0.0


@login_required
def resume_download_pdf(request, resume_id):
    """
    Generate (or serve cached) PDF for the resume. Template choice via ?template=modern|classic|minimal
    Use ?force=1 to bypass cache. Use ?debug_html=1 to return the HTML used for PDF generation.

    PDF renderer preference order:
      1) pdfkit (wkhtmltopdf) - recommended when wkhtmltopdf binary is installed
      2) weasyprint (if installed and working)
      3) xhtml2pdf / pisa fallback
    """
    resume = get_object_or_404(Resume, id=resume_id)
    if resume.owner != request.user and not (getattr(request.user, 'role', None) == 'hr' or getattr(request.user, 'is_staff', False)):
        return HttpResponseForbidden("Not allowed")

    template_key = request.GET.get('template', 'modern')
    template_file = TEMPLATE_MAP.get(template_key, TEMPLATE_MAP['modern'])

    safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in (resume.title or 'resume')).strip().replace(' ', '_')[:120]
    try:
        ts = int(resume.updated_at.timestamp())
    except Exception:
        ts = 0
    filename = f"{resume.owner.username}_r{resume.id}_{safe_title}_{template_key}_{ts}.pdf"

    media_subdir = os.path.join(settings.MEDIA_ROOT, 'resumes')
    os.makedirs(media_subdir, exist_ok=True)
    pdf_path = os.path.join(media_subdir, filename)

    force = request.GET.get('force') == '1'

    # --- compute mtimes to decide if cached PDF is stale ---
    template_mtime = _get_template_mtime(template_file)
    css_mtime = 0.0

    # Try to locate resume.css and get its mtime
    try:
        css_candidates = [
            os.path.join(settings.BASE_DIR, 'static', 'css', 'resume.css'),
            os.path.join(getattr(settings, 'STATIC_ROOT', '') or '', 'css', 'resume.css')
        ]
        for c in css_candidates:
            if c and os.path.exists(c):
                css_mtime = float(os.path.getmtime(c))
                break
        if not css_mtime:
            found_css = finders.find('css/resume.css') or finders.find('resume.css') or finders.find('jobs/css/resume.css')
            if found_css and os.path.exists(found_css):
                css_mtime = float(os.path.getmtime(found_css))
    except Exception:
        css_mtime = 0.0

    # If a cached PDF exists, check its mtime
    cached_pdf_mtime = 0.0
    if os.path.exists(pdf_path):
        try:
            cached_pdf_mtime = float(os.path.getmtime(pdf_path))
        except Exception:
            cached_pdf_mtime = 0.0

    # If template or css is newer than cached PDF, treat as stale.
    cache_is_stale = (template_mtime > cached_pdf_mtime) or (css_mtime > cached_pdf_mtime)

    # Serve cached file when available and not stale (unless forced)
    if not force and os.path.exists(pdf_path) and not cache_is_stale:
        logger.info("Serving cached resume PDF for resume_id=%s: %s (template_mtime=%s css_mtime=%s pdf_mtime=%s)", resume.id, pdf_path, template_mtime, css_mtime, cached_pdf_mtime)
        resp = FileResponse(open(pdf_path, 'rb'), content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp

    # If the file exists but is stale, remove older cached variants with same prefix to avoid duplicates
    try:
        if os.path.exists(pdf_path) and cache_is_stale:
            logger.info("Cached PDF stale (template/CSS changed). Removing old cache for resume_id=%s", resume.id)
            _clear_resume_cache(resume)
    except Exception:
        pass

    # Build cleaned copy of resume.data
    raw_data = resume.data or {}
    cleaned = json.loads(json.dumps(raw_data)) if raw_data else {}

    if cleaned.get('summary'):
        s = cleaned['summary'].strip()
        cleaned['summary'] = (s[:700].rsplit(' ', 1)[0] + '…') if len(s) > 700 else s

    MAX_BULLETS = 4
    MAX_BULLET_LEN = 220
    if cleaned.get('projects') and isinstance(cleaned['projects'], list):
        new_projects = []
        for p in cleaned['projects']:
            pcopy = dict(p) if isinstance(p, dict) else {}
            lines = []
            if isinstance(pcopy.get('description_lines'), list) and pcopy.get('description_lines'):
                lines = [str(x).strip() for x in pcopy.get('description_lines') if str(x).strip()]
            elif pcopy.get('description'):
                lines = [ln.strip() for ln in str(pcopy.get('description')).splitlines() if ln.strip()]
            trimmed = []
            for ln in lines[:MAX_BULLETS]:
                txt = ln
                if len(txt) > MAX_BULLET_LEN:
                    txt = txt[:MAX_BULLET_LEN].rsplit(' ', 1)[0] + '…'
                trimmed.append(txt)
            pcopy['description_lines'] = trimmed
            pcopy['description'] = '\n'.join(trimmed)
            new_projects.append(pcopy)
        cleaned['projects'] = new_projects

    if cleaned.get('achievements'):
        ach = str(cleaned['achievements']).strip()
        cleaned['achievements'] = (ach[:1200].rsplit(' ', 1)[0] + '…') if len(ach) > 1200 else ach

    context = {'resume': resume, 'data': cleaned}

    # Render fragment template (must be fragment-only)
    try:
        fragment_html = render_to_string(template_file, context=context, request=request)
    except Exception as e:
        logger.exception("Failed to render resume fragment template %s: %s", template_file, e)
        return HttpResponse("Template rendering error", status=500)

    # Inline resume.css if present but sanitize it first (used for Weasy)
    css_text = None
    try:
        candidates = [
            os.path.join(settings.BASE_DIR, 'static', 'css', 'resume.css'),
            os.path.join(getattr(settings, 'STATIC_ROOT', '') or '', 'css', 'resume.css')
        ]
        for c in candidates:
            if c and os.path.exists(c):
                with open(c, 'r', encoding='utf-8') as fh:
                    css_text = fh.read()
                    break
        if not css_text:
            found = finders.find('css/resume.css') or finders.find('resume.css') or finders.find('jobs/css/resume.css')
            if found and os.path.exists(found):
                with open(found, 'r', encoding='utf-8') as fh:
                    css_text = fh.read()
    except Exception:
        css_text = None

    # Remove external link to avoid fetch attempts
    fragment_html = re.sub(r'<link[^>]+resume\.css[^>]*>', '', fragment_html, flags=re.IGNORECASE)

    # We'll build two HTML variants:
    #  - final_html_weasy: includes sanitized CSS (for WeasyPrint)
    #  - final_html_pisa: strips all <style> blocks and injects only forced_css/pisa safe css (for pisa fallback)
    forced_css = """
    @page { size: A4; margin: 8mm 8mm 8mm 8mm; }
    html, body { font-family: "DejaVu Sans", "Helvetica", Arial, sans-serif; font-size: 9.6pt; color: #222; line-height:1.12; }
    .page { max-width: 760px; margin: 0 auto; box-sizing: border-box; }
    .para { white-space: pre-wrap; word-break: break-word; hyphens: auto; }
    """

    # Weasy HTML (inject sanitized css_text if found)
    if css_text:
        safe_css = _sanitize_css_for_pisa(css_text)
        fragment_html_with_css = "<style>\n" + safe_css + "\n</style>\n" + fragment_html
    else:
        fragment_html_with_css = fragment_html
    fragment_html_with_css = "<style>\n" + forced_css + "\n</style>\n" + fragment_html_with_css
    final_html_weasy = _normalize_html_for_pdf(fragment_html_with_css, include_css=True)

    # Pisa-friendly minimal fragment (we create a simple, stable layout)
    minimal_fragment = re.sub(r'<style[\s\S]*?</style>', '', fragment_html, flags=re.IGNORECASE)
    # Use a conservative CSS useful for fallback
    pisa_safe_css = r"""
@page { size: A4; margin: 8mm 8mm 8mm 8mm; }
html, body { font-family: "DejaVu Sans", "Helvetica", Arial, sans-serif; font-size: 10pt; color: #222; }
.container { max-width: 760px; margin: 0 auto; box-sizing: border-box; }
.header { text-align: center; margin-bottom: 8px; }
.name { font-size: 20pt; font-weight: 700; color: #0b3d91; margin: 0; }
.contact { font-size: 9pt; color: #444; margin-top: 4px; }
.layout-table { width: 100%; border-collapse: collapse; }
.leftcol { width: 28%; vertical-align: top; padding-right: 10px; font-size: 9.2pt; color:#333; }
.rightcol { width: 72%; vertical-align: top; font-size: 10pt; color:#111; }
.section-title { font-weight:700; color:#0b3d91; font-size:10pt; margin-bottom:6px; padding-bottom:2px; border-bottom:1px solid #efefef; text-transform:uppercase; }
.item-title { font-weight:700; font-size:10pt; margin:0 0 4px 0; }
.item-sub { color:#666; font-size:9pt; margin-bottom:6px; }
.para { margin:4px 0 8px 0; white-space: pre-wrap; text-align:justify; font-size:9.8pt; }
.ul { margin:6px 0 8px 18px; font-size:9.6pt; }
.ul li { margin-bottom:4px; }
.datecol { text-align:right; color:#666; font-size:9pt; white-space:nowrap; }
.item, .section { page-break-inside: avoid; }
"""

    # Heuristic split for left/right columns (if templates include .left / .right)
    header_html = ""
    m_name = re.search(r'(<div[^>]*class=["\']?name["\']?[^>]*>[\s\S]*?</div>)', minimal_fragment, flags=re.IGNORECASE)
    if m_name:
        header_html = m_name.group(1)
    # extract left if present
    m_left = re.search(r'(<div[^>]*class=["\']?left["\']?[^>]*>[\s\S]*?</div>)', minimal_fragment, flags=re.IGNORECASE)
    if m_left:
        left_html = m_left.group(1)
        right_html = re.sub(re.escape(left_html), '', minimal_fragment, flags=re.IGNORECASE)
    else:
        # fallback: try splitting at Profile/Experience heading or put everything on right
        idx = minimal_fragment.lower().find('profile')
        if idx and idx > 50:  # simple heuristic
            left_html = minimal_fragment[:idx]
            right_html = minimal_fragment[idx:]
        else:
            left_html = ""
            right_html = minimal_fragment

    wrapped = "<div class='container'>"
    if header_html:
        wrapped += "<div class='header'>" + header_html + "</div>"
    wrapped += "<table class='layout-table'><tr>"
    wrapped += "<td class='leftcol'>" + (left_html or "") + "</td>"
    wrapped += "<td class='rightcol'>" + (right_html or "") + "</td>"
    wrapped += "</tr></table></div>"

    fragment_for_pisa = "<style>\n" + pisa_safe_css + "\n</style>\n" + wrapped
    final_html_pisa = _normalize_html_for_pdf(fragment_for_pisa, include_css=False)

    if request.GET.get('debug_html') == '1':
        return HttpResponse("<h2>Weasy-friendly HTML</h2><hr>" + final_html_weasy + "<hr><h2>Pisa-friendly HTML</h2><hr>" + final_html_pisa, content_type='text/html')

    base_url = request.build_absolute_uri('/')

    # ---------- Try pdfkit / wkhtmltopdf first (recommended) ----------
    # find wkhtmltopdf path (look at settings.WKHTMLTOPDF_CMD or which)
    wkhtmltopdf_cmd = getattr(settings, 'WKHTMLTOPDF_CMD', None)
    if not wkhtmltopdf_cmd:
        wkhtmltopdf_cmd = shutil.which('wkhtmltopdf') or shutil.which('wkhtmltopdf.exe')
    if wkhtmltopdf_cmd:
        try:
            import pdfkit
            # build final html for pdfkit: use final_html_weasy if CSS included, else final_html_pisa
            html_for_pdfkit = final_html_weasy or final_html_pisa
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_cmd)
            options = {
                'quiet': '',
                'enable-local-file-access': None,  # allow local CSS/assets if needed
                'margin-top': '8mm',
                'margin-bottom': '8mm',
                'margin-left': '8mm',
                'margin-right': '8mm',
                'page-size': 'A4',
            }
            # generate PDF bytes
            pdf_bytes = pdfkit.from_string(html_for_pdfkit, False, options=options, configuration=config)
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)
            logger.info("Generated PDF (pdfkit/wkhtmltopdf) for resume_id=%s -> %s", resume.id, pdf_path)
            resp = FileResponse(open(pdf_path, 'rb'), content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="{filename}"'
            return resp
        except Exception as e:
            logger.debug("pdfkit/wkhtmltopdf generation failed: %s", e, exc_info=True)
    else:
        logger.debug("wkhtmltopdf binary not found (pdfkit will not be used).")

    # ---------- Try WeasyPrint next ----------
    try:
        from weasyprint import HTML  # type: ignore
        html_obj = HTML(string=final_html_weasy, base_url=base_url)
        pdf_bytes = html_obj.write_pdf()
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)
        logger.info("Generated PDF (weasyprint) for resume_id=%s -> %s", resume.id, pdf_path)
        resp = FileResponse(open(pdf_path, 'rb'), content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
    except Exception:
        logger.debug("WeasyPrint generation failed or not available; falling back to pisa.", exc_info=True)

    # ---------- Final fallback: xhtml2pdf / pisa ----------
    try:
        from xhtml2pdf import pisa  # type: ignore
        result = BytesIO()
        pisa_status = pisa.CreatePDF(final_html_pisa, dest=result, link_callback=lambda uri, rel: _link_callback(uri, rel, request))
        if getattr(pisa_status, 'err', None):
            logger.error("pisa reported errors while generating PDF for resume_id=%s", resume.id)
            return HttpResponse(final_html_pisa, content_type='text/html', status=500)
        with open(pdf_path, 'wb') as f:
            f.write(result.getvalue())
        logger.info("Generated PDF (xhtml2pdf) for resume_id=%s -> %s", resume.id, pdf_path)
        resp = FileResponse(open(pdf_path, 'rb'), content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
    except Exception as e:
        logger.exception("PDF generation final fallback error: %s", e)
        return HttpResponse(final_html_pisa, content_type='text/html', status=500)


# -------------------------
# Job CRUD (unchanged)
# -------------------------
@login_required
@hr_required
def job_create(request):
    if request.method == 'POST':
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.hr = request.user
            job.save()
            messages.success(request, "Job posted successfully.")
            return redirect('job_detail', job_id=job.id)
    else:
        form = JobForm()
    return render(request, 'jobs/job_post.html', {'form': form})


@login_required
@hr_required
def job_edit(request, job_id):
    job = get_object_or_404(Job, id=job_id, hr=request.user)
    if request.method == 'POST':
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, "Job updated.")
            return redirect('job_detail', job_id=job.id)
    else:
        form = JobForm(instance=job)
    return render(request, 'jobs/job_post.html', {'form': form, 'job': job})


@login_required
@hr_required
def job_delete(request, job_id):
    job = get_object_or_404(Job, id=job_id, hr=request.user)
    if request.method == 'POST':
        job.delete()
        messages.success(request, "Job deleted.")
        return redirect('hr_dashboard')
    return render(request, 'jobs/job_confirm_delete.html', {'job': job})


@login_required
def job_list(request):
    """
    Show only open jobs the current user has NOT already applied for.
    HR/staff users still see all listings.
    """
    qs = Job.objects.filter(is_active=True).order_by('-created_at')
    q = request.GET.get('q', '').strip()
    skill = request.GET.get('skill', '').strip()
    location = request.GET.get('location', '').strip()

    # --- Search filters ---
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(company__icontains=q) |
            Q(description__icontains=q)
        )

    if skill:
        try:
            qs = qs.filter(required_skills__contains=[skill])
        except Exception:
            qs = qs.filter(
                Q(description__icontains=skill) |
                Q(title__icontains=skill)
            )

    if location:
        qs = qs.filter(location__icontains=location)

    # --- Exclude jobs already applied for (non-HR users only) ---
    user = request.user
    if user.is_authenticated and not (getattr(user, 'role', None) == 'hr' or user.is_staff):
        applied_ids = Application.objects.filter(student=user).values_list('job_id', flat=True)
        qs = qs.exclude(id__in=applied_ids)

    # --- Only show open jobs ---
    jobs = [job for job in qs if job.is_open()]

    return render(
        request,
        'jobs/job_list.html',
        {'jobs': jobs, 'q': q, 'skill': skill, 'location': location}
    )


@login_required
def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    is_open = job.is_open()
    return render(request, 'jobs/job_detail.html', {'job': job, 'is_open': is_open})


# -------------------------
# HR: applications views (unchanged)
# -------------------------
@login_required
@hr_required
def hr_applications_for_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    if job.hr != request.user:
        return HttpResponseForbidden("Not allowed")
    applications = Application.objects.filter(job=job).select_related('student', 'resume').order_by('-applied_at')
    return render(request, 'jobs/hr_applications_list.html', {'job': job, 'applications': applications})


@login_required
@hr_required
def hr_application_detail(request, app_id):
    app = get_object_or_404(Application, id=app_id)
    job = app.job
    if job.hr != request.user:
        return HttpResponseForbidden("Not allowed")

    # lazy import email utils to avoid import-time failure if module missing
    try:
        from .email_utils import send_shortlist_email, send_reject_email
    except Exception:
        send_shortlist_email = None
        send_reject_email = None

    if request.method == 'POST':
        if 'shortlist' in request.POST:
            form = ShortlistForm(request.POST)
            if form.is_valid():
                date = form.cleaned_data['interview_date']
                t = form.cleaned_data['interview_time']
                interview_dt = datetime.combine(date, t)
                message = form.cleaned_data.get('message') or ''
                meeting_link = form.cleaned_data.get('meeting_link') or ''
                try:
                    if send_shortlist_email is None:
                        raise RuntimeError("Email helper not available on server.")
                    send_shortlist_email(
                        student_email=app.student.email,
                        student_name=app.student.get_full_name() or app.student.username,
                        hr_name=request.user.get_full_name() or request.user.username,
                        job_title=job.title,
                        interview_dt=interview_dt,
                        meeting_link=meeting_link,
                        message=message
                    )
                    app.status = 'shortlisted'
                    app.save()
                    messages.success(request, "Student shortlisted and email sent.")
                    return redirect('hr_application_detail', app_id=app.id)
                except Exception as e:
                    messages.error(request, f"Failed to send email: {e}")
        elif 'reject' in request.POST:
            reason = request.POST.get('reject_message', '')
            try:
                if send_reject_email is None:
                    raise RuntimeError("Email helper not available on server.")
                send_reject_email(
                    student_email=app.student.email,
                    student_name=app.student.get_full_name() or app.student.username,
                    hr_name=request.user.get_full_name() or request.user.username,
                    job_title=job.title,
                    message=reason
                )
                app.status = 'rejected'
                app.save()
                messages.success(request, "Applicant rejected and email sent.")
                return redirect('hr_applications_for_job', job_id=job.id)
            except Exception as e:
                messages.error(request, f"Failed to send reject email: {e}")
    else:
        form = ShortlistForm()

    return render(request, 'jobs/hr_application_detail.html', {'app': app, 'form': form})


# -------------------------
# Application flow (unchanged)
# -------------------------
@login_required
def apply_start(request, job_id):
    job = get_object_or_404(Job, id=job_id, is_active=True)
    if not job.is_open():
        messages.error(request, "This job is not accepting applications.")
        return redirect('job_detail', job_id=job.id)

    my_resumes = Resume.objects.filter(owner=request.user).order_by('-updated_at')

    if request.method == 'GET':
        form = ApplyChooseForm()
        return render(request, 'jobs/apply_start.html', {'job': job, 'resumes': my_resumes, 'form': form})

    uploaded_file = None
    form = ApplyChooseForm(request.POST, request.FILES)
    action = request.POST.get('action', 'score')
    if not form.is_valid():
        return render(request, 'jobs/apply_start.html', {'job': job, 'resumes': my_resumes, 'form': form})

    uploaded_file = form.cleaned_data.get('uploaded_resume')
    resume_choice_raw = (request.POST.get('resume_choice') or form.cleaned_data.get('resume_id') or '')
    resume_choice_raw = str(resume_choice_raw).strip()
    resume_id = None
    if resume_choice_raw:
        try:
            resume_id = int(resume_choice_raw)
        except Exception:
            resume_id = None

    chosen_resume = None
    uploaded_present = bool(uploaded_file)
    resume_selected = bool(resume_id)
    if uploaded_present == resume_selected:
        form.add_error(None, "Please provide exactly one resume option: choose a saved resume OR upload a file (not both or neither).")
        return render(request, 'jobs/apply_start.html', {'job': job, 'resumes': my_resumes, 'form': form})

    resume_text = ''
    if resume_id:
        try:
            chosen_resume = Resume.objects.get(id=resume_id, owner=request.user)
            resume_text = resume_json_to_text(chosen_resume.data or {})
        except Resume.DoesNotExist:
            chosen_resume = None
            resume_text = ''
    elif uploaded_file:
        try:
            resume_text = extract_text(uploaded_file) or ''
        except Exception:
            resume_text = ''
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    job_keywords = job.required_skills or []
    if not job_keywords:
        tokens = re.findall(r'\b[a-zA-Z0-9+#\.\-]+\b', job.description.lower())
        job_keywords = sorted(set([t for t in tokens if len(t) > 2]))[:40]

    score, matched, missing = compute_ats_score(job_keywords, resume_text)

    if action == 'score':
        return render(request, 'jobs/apply_confirm.html', {
            'job': job,
            'score': score,
            'matched': matched,
            'missing': missing,
            'form': form,
            'chosen_resume': chosen_resume,
            'uploaded_exists': bool(uploaded_file),
            'resumes': my_resumes,
        })

    if action == 'confirm':
        application = Application.objects.create(
            student=request.user,
            job=job,
            resume=chosen_resume,
            cover_letter=form.cleaned_data.get('cover_letter', ''),
            ats_score=score,
            matched_keywords=matched,
            missing_keywords=missing
        )
        if uploaded_file:
            application.uploaded_resume.save(uploaded_file.name, uploaded_file, save=True)
        messages.success(request, "Application submitted successfully.")
        return redirect('student_applications')

    # ✅ FINAL FALLBACK RETURN (fixes your error)
    return render(request, 'jobs/apply_start.html', {
        'job': job,
        'resumes': my_resumes,
        'form': form
    })

@login_required
def student_applications(request):
    apps = Application.objects.filter(student=request.user).select_related('job').order_by('-applied_at')
    return render(request, 'jobs/student_applications.html', {'applications': apps})
