"""Стартовые MessageTemplate'ы и PushRule'ы для автопушей менеджерам."""

from django.db import migrations


TEMPLATES = [
    {
        "code": "placement_stale_to_manager",
        "name": "Зависшая связка → менеджеру",
        "audience": "MANAGER",
        "text": (
            "По {student_name} в {company_name} нет решения уже {days} дней. "
            "Стоит пушнуть."
        ),
    },
    {
        "code": "placement_overdue_internship",
        "name": "Превышен срок стажировки → менеджеру",
        "audience": "MANAGER",
        "text": (
            "Стажировка {student_name} в {company_name} превысила плановый "
            "срок ({planned_days} дн)."
        ),
    },
    {
        "code": "company_paused_long",
        "name": "Компания давно на паузе → менеджеру",
        "audience": "MANAGER",
        "text": "Компания {company_name} на паузе уже {days} дней. Уточнить статус?",
    },
]


RULES = [
    {
        "name": "Зависшие резюме",
        "trigger_type": "PLACEMENT_STATUS_STALE",
        "target_status": "SENT_TO_COMPANY",
        "days_threshold": 14,
        "template_code": "placement_stale_to_manager",
    },
    {
        "name": "Превышен срок стажировки",
        "trigger_type": "PLACEMENT_DURATION_EXCEEDED",
        "target_status": "",
        "days_threshold": 0,
        "template_code": "placement_overdue_internship",
    },
    {
        "name": "Затянувшаяся пауза компании",
        "trigger_type": "COMPANY_PAUSED_STALE",
        "target_status": "",
        "days_threshold": 30,
        "template_code": "company_paused_long",
    },
]


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("notifications", "MessageTemplate")
    PushRule = apps.get_model("notifications", "PushRule")

    code_to_template = {}
    for spec in TEMPLATES:
        template, _ = MessageTemplate.objects.update_or_create(
            code=spec["code"],
            defaults={
                "name": spec["name"],
                "audience": spec["audience"],
                "text": spec["text"],
                "is_active": True,
            },
        )
        code_to_template[spec["code"]] = template

    for spec in RULES:
        PushRule.objects.update_or_create(
            name=spec["name"],
            defaults={
                "trigger_type": spec["trigger_type"],
                "target_status": spec["target_status"],
                "days_threshold": spec["days_threshold"],
                "template": code_to_template[spec["template_code"]],
                "is_active": True,
            },
        )


def unseed(apps, schema_editor):
    MessageTemplate = apps.get_model("notifications", "MessageTemplate")
    PushRule = apps.get_model("notifications", "PushRule")

    PushRule.objects.filter(name__in=[r["name"] for r in RULES]).delete()
    MessageTemplate.objects.filter(code__in=[t["code"] for t in TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
