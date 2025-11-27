# interview/views.py
from io import BytesIO
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q

from .models import InterviewQuestion
from .utils import render_to_pdf


@login_required
def index(request):
    """
    Interview prep search/filter page.
    Default: search by role/keyword only.
    Users can further filter by category or tag if they want.
    """
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    tag = request.GET.get('tag', '').strip()

    qs = InterviewQuestion.objects.all().order_by('-created_at')

    # Always apply role/keyword filter first
    if q:
        qs = qs.filter(
            Q(role__icontains=q) |
            Q(question__icontains=q) |
            Q(tags__icontains=q)
        )

    # Only apply category if user explicitly selects it
    if category:
        qs = qs.filter(category=category)

    # Only apply tag if user selects it
    if tag:
        qs = qs.filter(tags__icontains=tag)

    # paginate
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))  # smaller page size for UI
    except ValueError:
        page, page_size = 1, 10

    paginator = Paginator(qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(
        request,
        "interview/index.html",
        {
            "questions": page_obj.object_list,
            "q": q,
            "category": category,
            "tag": tag,
            "page_obj": page_obj,
        },
    )


@login_required
def question_detail(request, pk):
    """
    Show detail page for a single question.
    """
    q = get_object_or_404(InterviewQuestion, pk=pk)
    return render(request, "interview/question_detail.html", {"question": q})


@login_required
def api_search(request):
    """
    JSON API for searching/filtering questions.
    """
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    tag = request.GET.get("tag", "").strip()

    qs = InterviewQuestion.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(
            Q(role__icontains=q)
            | Q(question__icontains=q)
            | Q(tags__icontains=q)
        )
    if category:
        qs = qs.filter(category=category)
    if tag:
        qs = qs.filter(tags__icontains=tag)

    # pagination
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 25))
    except ValueError:
        page, page_size = 1, 25
    paginator = Paginator(qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    results = []
    for it in page_obj.object_list:
        results.append(
            {
                "id": it.id,
                "role": it.role,
                "category": it.category,
                "question": it.question,
                # hide answer unless ?include_answer=1
                "answer": it.answer
                if request.GET.get("include_answer") == "1"
                else "",
                "tags": it.tag_list()
                if hasattr(it, "tag_list")
                else (it.tags or "").split(","),
                "source": it.source,
                "difficulty": it.difficulty,
            }
        )

    return JsonResponse(
        {
            "count": paginator.count,
            "num_pages": paginator.num_pages,
            "page": page_obj.number,
            "page_size": page_obj.paginator.per_page,
            "results": results,
        }
    )


@login_required
def question_pdf(request, pk):
    """
    Generate a PDF for a single question and return it inline or as attachment.
    Query params:
      - download=1  -> set Content-Disposition to attachment (download)
      - answer=1    -> include the answer in the generated PDF
    """
    q = get_object_or_404(InterviewQuestion, pk=pk)
    include_answer = request.GET.get("answer") == "1"
    context = {
        "question": q,
        "include_answer": include_answer,
        "user": request.user,
    }
    pdf_bytes = render_to_pdf("interview/question_pdf.html", context)
    if not pdf_bytes:
        return HttpResponse("Failed to generate PDF", status=500)

    filename = f"question_{q.id}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    disposition = (
        "attachment" if request.GET.get("download") == "1" else "inline"
    )
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response
