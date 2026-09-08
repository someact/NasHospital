import os
import json
import hashlib
import tarfile
import tempfile
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.utils import timezone


def compute_sha256(filepath):
    """Computes SHA-256 hex digest for a file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


class Command(BaseCommand):
    help = "Creates a disaster recovery backup archive of the MedResearch DMS database and encrypted protected media with SHA-256 checksums."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help="Custom output file path for the .tar.gz archive."
        )
        parser.add_argument(
            '--no-media',
            action='store_true',
            help="Exclude protected encrypted media files from the backup."
        )

    def handle(self, *args, **options):
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = getattr(settings, 'BACKUP_DIR', settings.BASE_DIR / 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        output_path = options.get('output')
        if not output_path:
            output_path = os.path.join(backup_dir, f"dms_backup_{timestamp}.tar.gz")
        elif os.path.isdir(output_path):
            output_path = os.path.join(output_path, f"dms_backup_{timestamp}.tar.gz")

        include_media = not options.get('no_media', False)
        media_root = getattr(settings, 'PROTECTED_MEDIA_ROOT', settings.BASE_DIR / 'protected_media')

        self.stdout.write(self.style.NOTICE(f"Initiating MedResearch DMS backup at {timestamp}..."))

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Database dump
            db_dump_path = os.path.join(tmp_dir, 'db_dump.json')
            self.stdout.write("Dumping database tables (accounts, papers)...")
            with open(db_dump_path, 'w', encoding='utf-8') as f:
                call_command('dumpdata', 'accounts', 'papers', format='json', indent=2, stdout=f)

            db_sha256 = compute_sha256(db_dump_path)

            # 2. Collect media files
            media_manifest = []
            tmp_media_dir = os.path.join(tmp_dir, 'protected_media')
            os.makedirs(tmp_media_dir, exist_ok=True)

            if include_media and os.path.exists(media_root):
                self.stdout.write("Collecting and hashing encrypted media files...")
                for root, _, files in os.walk(media_root):
                    for filename in files:
                        src_file = os.path.join(root, filename)
                        rel_path = os.path.relpath(src_file, media_root)

                        # Storage Encryption Integrity Guard (SEC-05):
                        # Verify file is not an unencrypted plaintext PDF
                        with open(src_file, 'rb') as f_check:
                            header = f_check.read(16)
                            if header.startswith(b'%PDF-'):
                                raise CommandError(
                                    f"Security Violation: Plaintext unencrypted PDF file detected in protected storage: '{rel_path}'. "
                                    f"Backup aborted to prevent unencrypted clinical data leakage."
                                )

                        dest_file = os.path.join(tmp_media_dir, rel_path)
                        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                        shutil.copy2(src_file, dest_file)

                        file_sha256 = compute_sha256(dest_file)
                        media_manifest.append({
                            'relative_path': rel_path,
                            'sha256': file_sha256,
                            'size_bytes': os.path.getsize(dest_file)
                        })

            # 3. Create manifest
            manifest = {
                'backup_version': '1.0',
                'system': 'MedResearch DMS',
                'created_at': timezone.now().isoformat(),
                'database_dump': {
                    'filename': 'db_dump.json',
                    'sha256': db_sha256,
                    'size_bytes': os.path.getsize(db_dump_path)
                },
                'media_files': media_manifest,
                'media_files_count': len(media_manifest)
            }

            manifest_path = os.path.join(tmp_dir, 'manifest.json')
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)

            # 4. Create tar.gz archive
            self.stdout.write(f"Compressing archive to {output_path}...")
            with tarfile.open(output_path, 'w:gz') as tar:
                tar.add(manifest_path, arcname='manifest.json')
                tar.add(db_dump_path, arcname='db_dump.json')
                if os.path.exists(tmp_media_dir):
                    tar.add(tmp_media_dir, arcname='protected_media')

        archive_size_kb = os.path.getsize(output_path) / 1024
        self.stdout.write(self.style.SUCCESS(
            f"Successfully created backup archive: {output_path} "
            f"({archive_size_kb:.1f} KB, {len(media_manifest)} media files backed up)"
        ))
