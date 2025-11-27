# interview/management/commands/import_questions.py
import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# adjust import path to your model
from interview.models import InterviewQuestion

class Command(BaseCommand):
    help = (
        "Import interview questions from a JSON file.\n\n"
        "Expected format: a JSON array of objects like:\n"
        '[{"role":"Python Dev","category":"pyq","question":"Q...","answer":"A...","tags":"python,gil","source":"notes","difficulty":"easy"}, ...]\n'
        "This command will create questions if the exact role+question doesn't already exist."
    )

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='Path to the JSON file to import.')
        parser.add_argument('--update', action='store_true', help='Update existing questions (match by role+question).')
        parser.add_argument('--skip-if-exists', action='store_true', help='Skip creating items if an exact role+question exists (default behavior).')

    def handle(self, *args, **options):
        path = options['path']
        update = options['update']
        skip_if_exists = options['skip_if_exists']

        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as exc:
            raise CommandError(f"Failed to load JSON: {exc}")

        if not isinstance(data, list):
            raise CommandError("JSON root must be a list/array of question objects.")

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        for idx, item in enumerate(data, start=1):
            try:
                role = str(item.get('role','')).strip()
                question_text = str(item.get('question','')).strip()
                if not role or not question_text:
                    self.stderr.write(f"[{idx}] Skipping: missing role or question.")
                    skipped += 1
                    continue

                defaults = {
                    'category': item.get('category','important') or 'important',
                    'answer': item.get('answer','') or '',
                    'tags': item.get('tags','') or '',
                    'source': item.get('source','') or '',
                    'difficulty': item.get('difficulty','') or '',
                }

                # match by role + question text to avoid duplicates
                existing = InterviewQuestion.objects.filter(role=role, question=question_text).first()

                if existing:
                    if update:
                        for k, v in defaults.items():
                            setattr(existing, k, v)
                        existing.save()
                        updated += 1
                        self.stdout.write(f"[{idx}] Updated: role='{role}'")
                    else:
                        skipped += 1
                        if not skip_if_exists:
                            self.stdout.write(f"[{idx}] Exists, skipped: role='{role}'")
                        else:
                            self.stdout.write(f"[{idx}] Exists, skip-if-exists set.")
                    continue

                InterviewQuestion.objects.create(role=role, question=question_text, **defaults)
                created += 1
                self.stdout.write(f"[{idx}] Created: role='{role}'")

            except Exception as e:
                errors += 1
                self.stderr.write(f"[{idx}] ERROR: {e}")

        self.stdout.write(self.style.SUCCESS(f"Import finished. Created={created}, Updated={updated}, Skipped={skipped}, Errors={errors}"))
