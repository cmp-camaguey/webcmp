from django.db import migrations


PAGE_KEYS = [
    'vision',
    'mission',
    'about',
    'institutional_information',
    'legal_notice',
    'data_subject_rights',
    'cookie_policy',
    'privacy_policy',
]


def seed_pages(apps, schema_editor):
    InstitutionalPage = apps.get_model('core', 'InstitutionalPage')
    for key in PAGE_KEYS:
        InstitutionalPage.objects.get_or_create(page_key=key, defaults={'blocks': {}})


def unseed_pages(apps, schema_editor):
    InstitutionalPage = apps.get_model('core', 'InstitutionalPage')
    InstitutionalPage.objects.filter(page_key__in=PAGE_KEYS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0021_add_institutional_page'),
    ]

    operations = [
        migrations.RunPython(seed_pages, unseed_pages),  # data-safety: reviewed: seeds empty institutional page records; reverse removes only those seeded keys
    ]
