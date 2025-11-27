# jobs/utils.py
import re
import os
import tempfile

# rapidfuzz for fuzzy matching. If not installed, we'll fall back to simple checks.
try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except Exception:
    fuzz = None
    _HAS_RAPIDFUZZ = False

# PDF/DOCX extraction libs
try:
    from pdfminer.high_level import extract_text as extract_text_from_pdf
except Exception:
    extract_text_from_pdf = None

try:
    import docx
except Exception:
    docx = None


def extract_text_from_docx(file_path_or_fileobj):
    """
    Accepts a path or file-like; returns concatenated paragraph text.
    """
    tmp_created = False
    path = None
    try:
        if hasattr(file_path_or_fileobj, 'read'):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
            tmp.write(file_path_or_fileobj.read())
            tmp.close()
            path = tmp.name
            tmp_created = True
        else:
            path = file_path_or_fileobj

        if docx is None:
            return ''

        doc = docx.Document(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return '\n'.join(paragraphs)
    finally:
        if tmp_created and path:
            try:
                os.unlink(path)
            except Exception:
                pass


def extract_text(file_field):
    """
    Given a Django UploadedFile or file-like object, write to temp file and extract text.
    Supports .pdf and .docx (best-effort).
    Returns extracted text (string). Resets file_field pointer if possible.
    """
    # Determine name
    name = getattr(file_field, 'name', '') or ''
    name = name.lower()
    suffix = '.pdf' if name.endswith('.pdf') else '.docx'

    tmp = None
    tmp_name = None
    try:
        # Read uploaded bytes and write to temp file
        data = file_field.read()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(data)
        tmp.flush()
        tmp.close()
        tmp_name = tmp.name

        text = ''
        if suffix == '.pdf' and extract_text_from_pdf is not None:
            try:
                text = extract_text_from_pdf(tmp_name) or ''
            except Exception:
                text = ''
        else:
            # DOCX
            text = extract_text_from_docx(tmp_name) or ''

        return text
    finally:
        # cleanup temp file
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
        # rewind original file if possible so it can be saved later
        try:
            file_field.seek(0)
        except Exception:
            pass


def resume_json_to_text(resume_json):
    """
    Convert structured resume JSON to plain text for matching.
    """
    parts = []
    personal = resume_json.get('personal', {})
    parts.append(personal.get('full_name',''))
    parts.append(personal.get('headline',''))
    parts.append(personal.get('location',''))
    parts.append(resume_json.get('summary',''))
    for e in resume_json.get('education', []):
        parts.append(' '.join(e.get(k,'') for k in ['school','degree','details','duration']))
    for ex in resume_json.get('experience', []):
        parts.append(' '.join(ex.get(k,'') for k in ['title','company','description','duration']))
    for p in resume_json.get('projects', []):
        parts.append(' '.join(p.get(k,'') for k in ['title','tech','description','duration']))
    parts.append(' '.join(resume_json.get('skills', [])))
    parts.append(resume_json.get('achievements',''))
    return '\n'.join([p for p in parts if p])


def normalize_tokens(text):
    """
    Basic tokenization for matching: keeps alnum, +, #, ., - characters.
    """
    if not text:
        return []
    tokens = re.findall(r'\b[a-zA-Z0-9+#\.\-]+\b', text.lower())
    return tokens


def compute_ats_score(job_keywords, resume_text, fuzzy_threshold=80):
    """
    Compute ATS score:
      - job_keywords: list[str]
      - resume_text: str
    Returns: (score_percent, matched_list, missing_list)
    Matching strategy:
      1) exact token match
      2) substring match
      3) fuzzy partial match (RapidFuzz) if available
    """
    resume_tokens = normalize_tokens(resume_text)
    rt = ' '.join(resume_tokens)
    matched = []
    missing = []

    for kw in job_keywords:
        if not kw:
            continue
        k = kw.strip().lower()
        matched_flag = False

        # exact token
        if k in resume_tokens:
            matched_flag = True
        # substring
        elif k in rt:
            matched_flag = True
        # fuzzy (if available)
        elif _HAS_RAPIDFUZZ and fuzz is not None:
            try:
                score = fuzz.partial_ratio(k, rt)
                if score >= fuzzy_threshold:
                    matched_flag = True
            except Exception:
                matched_flag = False

        if matched_flag:
            matched.append(kw)
        else:
            missing.append(kw)

    total = len(job_keywords) if job_keywords else 1
    score_percent = round(100.0 * (len(matched) / total), 1)
    return score_percent, matched, missing
