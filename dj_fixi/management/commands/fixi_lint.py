"""
manage.py fixi_lint [paths...] [--warnings-as-errors]

Lint template source for what fixi.js silently ignores, without rendering.
The test client lints every rendered response (the surface that matters);
this is the same rule set for a person at the command line, over every
project template directory by default and never site-packages.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from dj_fixi.lint import iter_template_files, lint_template_source, template_directories


class Command(BaseCommand):
    help = "Lint template source for what fixi.js silently ignores (htmx attributes, bad swaps, ...)."

    def add_arguments(self, parser):
        parser.add_argument(
            "paths",
            nargs="*",
            help="Template files or directories. Default: every project template directory.",
        )
        parser.add_argument(
            "--warnings-as-errors",
            action="store_true",
            help="Exit non-zero on warnings too.",
        )

    def handle(self, *args, paths, warnings_as_errors, **options):
        roots = [Path(p) for p in paths] or template_directories()
        files = []
        for root in roots:
            files += [root] if root.is_file() else list(iter_template_files([root]))
        errors = warnings = 0
        for path in files:
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self.stderr.write(f"{path}: {exc}")
                continue
            for finding in lint_template_source(source, file=str(path)):
                if finding.level == "error" or warnings_as_errors:
                    errors += 1
                    self.stdout.write(self.style.ERROR(str(finding)))
                else:
                    warnings += 1
                    self.stdout.write(self.style.WARNING(str(finding)))
        self.stdout.write(
            f"fixi_lint: {len(files)} template(s), {errors} error(s), {warnings} warning(s)"
        )
        if errors:
            raise CommandError(f"{errors} error(s); see dj_fixi.lint.FINDING_IDS")
