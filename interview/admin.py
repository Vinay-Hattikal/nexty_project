# interview/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import InterviewQuestion

@admin.register(InterviewQuestion)
class InterviewQuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'role', 'short_question', 'category', 'difficulty', 'pdf_link')
    search_fields = ('role', 'question', 'tags')
    list_filter = ('category', 'difficulty')

    def short_question(self, obj):
        return obj.question[:60]
    short_question.short_description = 'Question'

    def pdf_link(self, obj):
        return format_html('<a href="/interview/question/{}/pdf/?download=1">PDF</a>', obj.id)
    pdf_link.short_description = 'PDF'
