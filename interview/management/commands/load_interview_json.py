# interview/management/commands/load_interview_json.py
import json
import os
from typing import Dict, Tuple, List
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.text import Truncator

from interview.models import InterviewQuestion


def normalize_tags(value) -> str:
    """
    Accept CSV string or list; return normalized CSV:
    - strip whitespace
    - dedupe case-insensitively
    - preserve original casing of first occurrence
    """
    if not value:
        return ""
    if isinstance(value, list):
        parts = [str(p) for p in value]
    else:
        s = str(value)
        # if looks like JSON array string, try to load
        s_stripped = s.strip()
        if s_stripped.startswith("[") and s_stripped.endswith("]"):
            try:
                parsed = json.loads(s_stripped)
                parts = [str(p) for p in parsed]
            except Exception:
                parts = [p.strip() for p in s.split(",")]
        else:
            parts = [p.strip() for p in s.split(",")]

    seen = set()
    out = []
    for p in parts:
        if p is None:
            continue
        p = str(p).strip()
        if not p:
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return ",".join(out)


def key_for(item) -> Tuple[str, str]:
    """Return the duplicate-detection key (lowercased role, lowercased question)."""
    role = (item.get("role") or "").strip()
    question = (item.get("question") or "").strip()
    return role.lower(), question.lower()


class Command(BaseCommand):
    help = 'Load interview questions from JSON file. Usage: manage.py load_interview_json path/to/questions.json [--clear] [--batch-size=N]'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to JSON file containing questions.')
        parser.add_argument('--clear', action='store_true', help='If set, delete existing questions before loading.')
        parser.add_argument('--batch-size', type=int, default=500, help='Batch size for bulk_create (default 500).')
        parser.add_argument('--dry-run', action='store_true', help='Validate and show summary but do not write to DB.')
        parser.add_argument('--force-update', action='store_true', help='Overwrite existing fields when updating (instead of only filling missing).')
        parser.add_argument('--max-items', type=int, default=0, help='If >0, limit processed items (useful for testing).')

    def validate_item(self, item):
        # Minimal validation: question required
        question = item.get('question') or ""
        if not question or not str(question).strip():
            return False, "Missing or empty 'question' field"
        return True, None

    def handle(self, *args, **opts):
        path = opts['json_file']
        clear = opts['clear']
        batch_size = max(1, int(opts['batch_size']))
        dry_run = opts['dry_run']
        force_update = opts['force_update']
        max_items = int(opts.get('max_items') or 0)

        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")

        # Load JSON (reads entire file)
        self.stdout.write(f"Loading JSON from: {path}")
        with open(path, 'r', encoding='utf-8') as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON: {e}")

        if not isinstance(data, list):
            raise CommandError("JSON root must be an array/list of question objects.")

        total = len(data)
        if max_items and max_items < total:
            self.stdout.write(f"Limiting to first {max_items} items (max-items provided).")
            data = data[:max_items]
            total = len(data)

        self.stdout.write(f"Items to process: {total}")

        if clear and not dry_run:
            self.stdout.write("Clearing existing InterviewQuestion rows (this is irreversible).")
            InterviewQuestion.objects.all().delete()

        # Build set of keys from input and fetch candidates to avoid N+1 queries
        keys = { key_for(item) for item in data }
        roles = { (item.get('role') or '').strip() for item in data }
        # Fetch potential existing rows by role (narrow down) - role matching case-insensitively
        existing_q = Q()
        for r in roles:
            if r:
                existing_q |= Q(role__iexact=r)
        existing_map: Dict[Tuple[str,str], InterviewQuestion] = {}
        if existing_q:
            qs_existing = InterviewQuestion.objects.filter(existing_q)
            # build mapping by lowercased (role,question)
            for ex in qs_existing:
                existing_map[(ex.role.strip().lower(), ex.question.strip().lower())] = ex

        to_create: List[InterviewQuestion] = []
        to_update: List[InterviewQuestion] = []
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = 0

        def process_item(idx, item):
            nonlocal created_count, updated_count, skipped_count, errors
            valid, err = self.validate_item(item)
            if not valid:
                self.stdout.write(self.style.WARNING(f"[{idx}] Skipping: {err}"))
                return

            role = (item.get('role') or '').strip()
            category = (item.get('category') or 'important').strip()
            question = (item.get('question') or '').strip()
            answer = item.get('answer') or ''
            tags = normalize_tags(item.get('tags', '') or '')
            source = item.get('source') or ''
            difficulty = item.get('difficulty') or ''

            key = (role.lower(), question.lower())
            existing = existing_map.get(key)

            if existing:
                # Update behavior
                updated = False
                # If force_update, overwrite; else only fill when existing field empty
                if force_update:
                    existing.category = category
                    existing.answer = answer
                    existing.tags = tags
                    existing.source = source
                    existing.difficulty = difficulty
                    updated = True
                else:
                    if answer and not existing.answer:
                        existing.answer = answer
                        updated = True
                    if tags and not existing.tags:
                        existing.tags = tags
                        updated = True
                    if source and not existing.source:
                        existing.source = source
                        updated = True
                    if difficulty and not existing.difficulty:
                        existing.difficulty = difficulty
                        updated = True
                    if category and existing.category != category:
                        existing.category = category
                        updated = True

                if updated:
                    to_update.append(existing)
                    updated_count += 1
                else:
                    skipped_count += 1
                return

            # else create new instance
            iq = InterviewQuestion(
                role=role,
                category=category,
                question=question,
                answer=answer,
                tags=tags,
                source=source,
                difficulty=difficulty
            )
            to_create.append(iq)
            created_count += 1
            # Add to existing_map so subsequent duplicates in file are considered 'existing'
            existing_map[key] = iq  # note: this maps to unsaved object; used to avoid duplicate creation in same run

        # Iterate and prepare create/update lists
        for idx, item in enumerate(data, start=1):
            try:
                process_item(idx, item)
            except Exception as e:
                errors += 1
                self.stderr.write(f"[{idx}] ERROR: {e}")

            # If we're accumulating many to_create/to_update, flush in batches
            if len(to_create) >= batch_size:
                if dry_run:
                    self.stdout.write(f"[DRY RUN] Would bulk_create {len(to_create)} records (processed {idx}/{total})")
                    to_create.clear()
                else:
                    with transaction.atomic():
                        InterviewQuestion.objects.bulk_create(to_create, batch_size=batch_size)
                    self.stdout.write(f"Inserted {created_count} so far... (processed {idx}/{total})")
                    to_create.clear()

            if len(to_update) >= batch_size:
                if dry_run:
                    self.stdout.write(f"[DRY RUN] Would bulk_update {len(to_update)} records (processed {idx}/{total})")
                    to_update.clear()
                else:
                    # bulk_update requires list of saved model instances; ensure they have PKs
                    # For our existing_map we mixed unsaved new instances - ensure only saved ones are in to_update
                    saved_updates = [u for u in to_update if getattr(u, 'pk', None)]
                    if saved_updates:
                        fields = ['category', 'answer', 'tags', 'source', 'difficulty']
                        with transaction.atomic():
                            InterviewQuestion.objects.bulk_update(saved_updates, fields, batch_size=batch_size)
                    else:
                        # fallback: individually save
                        with transaction.atomic():
                            for u in to_update:
                                u.save()
                    to_update.clear()

        # Final flush
        if to_create:
            if dry_run:
                self.stdout.write(f"[DRY RUN] Would bulk_create final {len(to_create)} records")
            else:
                with transaction.atomic():
                    InterviewQuestion.objects.bulk_create(to_create, batch_size=batch_size)
                self.stdout.write(f"Inserted final {len(to_create)} records")
            to_create.clear()

        if to_update:
            if dry_run:
                self.stdout.write(f"[DRY RUN] Would bulk_update final {len(to_update)} records")
            else:
                # Save remaining updates
                saved_updates = [u for u in to_update if getattr(u, 'pk', None)]
                if saved_updates:
                    fields = ['category', 'answer', 'tags', 'source', 'difficulty']
                    with transaction.atomic():
                        InterviewQuestion.objects.bulk_update(saved_updates, fields, batch_size=batch_size)
                else:
                    with transaction.atomic():
                        for u in to_update:
                            u.save()
            to_update.clear()

        # Print summary
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN complete — no DB changes were made."))
        self.stdout.write(self.style.SUCCESS(
            f"Done. Created (in file): {created_count}, Updated (in file): {updated_count}, Skipped: {skipped_count}, Errors: {errors}"
        ))
