import os
import json
import hashlib
import tarfile
import tempfile
import shutil
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings


def compute_sha256(filepath):
    """Computes SHA-256 hex digest for a file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


class Command(BaseCommand):
    help = "Restores MedResearch DMS database and encrypted protected media from a verified backup archive with SHA-256 manifest validation."

    def add_arguments(self, parser):
        parser.add_argument(
            'archive',
            type=str,
            help="Path to the .tar.gz backup archive."
        )
        parser.add_argument(
            '--no-media',
            action='store_true',
            help="Do not restore media files, only database."
        )

    def handle(self, *args, **options):
        archive_path = options['archive']
        if not os.path.exists(archive_path):
            raise CommandError(f"Backup archive does not exist at: {archive_path}")

        include_media = not options.get('no_media', False)
        media_root = getattr(settings, 'PROTECTED_MEDIA_ROOT', settings.BASE_DIR / 'protected_media')

        self.stdout.write(self.style.NOTICE(f"Inspecting backup archive: {archive_path}..."))

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Extract archive
            with tarfile.open(archive_path, 'r:gz') as tar:
                # Python 3.12+ safe extraction filter
                try:
                    tar.extractall(path=tmp_dir, filter='data')
                except TypeError:
                    tar.extractall(path=tmp_dir)

            manifest_path = os.path.join(tmp_dir, 'manifest.json')
            if not os.path.exists(manifest_path):
                raise CommandError("Archive is invalid: manifest.json not found in archive root.")

            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            self.stdout.write(f"Archive manifest validated. Backup created at: {manifest.get('created_at')}")

            # 2. Verify Database Dump Integrity
            db_info = manifest.get('database_dump', {})
            db_filename = db_info.get('filename', 'db_dump.json')
            db_dump_path = os.path.join(tmp_dir, db_filename)

            if not os.path.exists(db_dump_path):
                raise CommandError(f"Integrity failure: {db_filename} missing from extracted archive.")

            actual_db_sha256 = compute_sha256(db_dump_path)
            expected_db_sha256 = db_info.get('sha256')
            if actual_db_sha256 != expected_db_sha256:
                raise CommandError(
                    f"Database checksum verification failed!\n"
                    f"Expected: {expected_db_sha256}\n"
                    f"Actual:   {actual_db_sha256}"
                )
            self.stdout.write(self.style.SUCCESS("✓ Database dump SHA-256 checksum verified."))

            # 3. Verify Media Files Integrity
            media_files = manifest.get('media_files', [])
            restored_media_count = 0

            if include_media and media_files:
                self.stdout.write("Verifying integrity of encrypted media files...")
                for item in media_files:
                    rel_path = item['relative_path']
                    expected_sha = item['sha256']
                    extracted_file = os.path.join(tmp_dir, 'protected_media', rel_path)

                    if not os.path.exists(extracted_file):
                        raise CommandError(f"Integrity failure: Media file missing from archive: {rel_path}")

                    actual_sha = compute_sha256(extracted_file)
                    if actual_sha != expected_sha:
                        raise CommandError(
                            f"Media checksum verification failed for {rel_path}!\n"
                            f"Expected: {expected_sha}\n"
                            f"Actual:   {actual_sha}"
                        )

                self.stdout.write(self.style.SUCCESS(f"✓ All {len(media_files)} encrypted media files verified."))

                # Copy verified media files to destination
                os.makedirs(media_root, exist_ok=True)
                for item in media_files:
                    rel_path = item['relative_path']
                    src = os.path.join(tmp_dir, 'protected_media', rel_path)
                    dst = os.path.join(media_root, rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    restored_media_count += 1

                self.stdout.write(f"Restored {restored_media_count} encrypted media files to {media_root}")

            # 4. Restore Database via loaddata
            self.stdout.write("Loading database records into current database...")
            call_command('loaddata', db_dump_path)
            self.stdout.write(self.style.SUCCESS("✓ Database records restored successfully."))

        self.stdout.write(self.style.SUCCESS(
            f"MedResearch DMS Disaster Recovery restore completed successfully from {archive_path}!"
        ))
