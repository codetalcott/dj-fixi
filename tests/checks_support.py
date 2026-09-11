"""Shared settings overrides for the system-check tests (not collected)."""

from django.core.checks import run_checks

PAGE = "FULL {{ is_fx }}"
PARTIAL = "PARTIAL {{ is_fx }}"

#: locmem templates matching the names used by tests/urlconfs/views.py, so the
#: "good" fixtures resolve and the template checks stay quiet for them.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "good/list.html": PAGE,
                        "good/list_partial.html": PARTIAL,
                        "good/at_urlconf.html": PAGE,
                    },
                )
            ],
            "context_processors": ["django.template.context_processors.request"],
        },
    }
]

#: Same, minus the partial -- for exercising W202.
TEMPLATES_NO_PARTIAL = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {"good/list.html": PAGE, "good/at_urlconf.html": PAGE},
                )
            ],
            "context_processors": ["django.template.context_processors.request"],
        },
    }
]


def ids(messages):
    return sorted(m.id for m in messages)


def check_ids(**kwargs):
    """Sorted dj-fixi check IDs for the current settings."""
    return ids(run_checks(tags=["dj_fixi"], **kwargs))


def fs_templates(directory, files: dict) -> list:
    """A DjangoTemplates engine reading real files, for the checks that scan source."""
    from pathlib import Path

    for name, source in files.items():
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    return [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [str(directory)],
            "APP_DIRS": False,
            "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
        }
    ]


#: The two templates every "good" fixture view resolves against, as files.
GOOD_FILES = {"good/list.html": PAGE, "good/list_partial.html": PARTIAL, "good/at_urlconf.html": PAGE}
