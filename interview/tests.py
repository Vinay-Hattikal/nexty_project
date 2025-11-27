# interview/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import InterviewQuestion

User = get_user_model()

class PdfViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client = Client()
        self.client.login(username='tester', password='pass')
        self.q = InterviewQuestion.objects.create(role='python dev', category='pyq', question='What is GIL?', answer='Global Interpreter Lock', tags='python,gil')

    def test_question_pdf_inline(self):
        resp = self.client.get(reverse('interview:question_pdf', args=[self.q.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_question_pdf_download_with_answer(self):
        resp = self.client.get(reverse('interview:question_pdf', args=[self.q.id]) + '?download=1&answer=1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertEqual(resp['Content-Type'], 'application/pdf')
