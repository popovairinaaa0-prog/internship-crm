"""Создание групп ролей `admins` и `vip_managers` с раздачей прав."""

from django.db import migrations


# Кодовые имена прав, которые получает группа vip_managers.
# Формат: "<app_label>.<codename>"
VIP_PERMISSIONS = [
    # Студенты, компании, направления — только view
    "students.view_student",
    "students.view_direction",
    "students.view_telegraminvitetoken",
    "companies.view_company",
    "placements.view_placement",
    # Placement: разрешаем change, но в админке readonly_fields отрежет всё
    # кроме поля `status` (см. PlacementAdmin.get_readonly_fields)
    "placements.change_placement",
    # Уведомления
    "notifications.view_comment",
    "notifications.add_comment",
    "notifications.change_comment",
    "notifications.view_attachment",
    "notifications.view_messagetemplate",
    "notifications.view_pushrule",
    "notifications.view_pushsent",
    "notifications.view_broadcastjob",
    "notifications.view_broadcastdelivery",
    "notifications.view_manualcontact",
    "notifications.add_manualcontact",
]


def _ensure_permissions_created(apps):
    """Принудительно прогоняет create_permissions для всех приложений.

    Стандартный post_migrate сигнал срабатывает в конце команды migrate,
    после применения всех миграций. Эта data-миграция запускается раньше
    и без явного вызова не увидит созданные Permission-объекты.
    """
    from django.apps import apps as global_apps
    from django.contrib.auth.management import create_permissions

    for app_label in (
        "auth",
        "contenttypes",
        "accounts",
        "students",
        "companies",
        "placements",
        "notifications",
    ):
        try:
            app_config = global_apps.get_app_config(app_label)
        except LookupError:
            continue
        create_permissions(app_config, verbosity=0)


def create_groups(apps, schema_editor):
    _ensure_permissions_created(apps)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("accounts", "User")

    admins, _ = Group.objects.get_or_create(name="admins")
    vip, _ = Group.objects.get_or_create(name="vip_managers")

    # admins — все права на всё
    admins.permissions.set(Permission.objects.all())

    # vip_managers — точечный набор по списку
    perms = []
    for label in VIP_PERMISSIONS:
        app_label, codename = label.split(".", 1)
        try:
            perms.append(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        except Permission.DoesNotExist:
            # Pragmatic: если право вдруг не создано (модель убрали),
            # просто пропускаем — миграция не должна падать на этом.
            continue
    vip.permissions.set(perms)

    # Существующих суперюзеров кладём в admins — для удобства проверок
    # «принадлежит ли пользователь группе admins». На реальные права это
    # не влияет: суперюзеры всё равно обходят permission-проверки.
    for su in User.objects.filter(is_superuser=True):
        su.groups.add(admins)


def drop_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["admins", "vip_managers"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_managerinvitetoken"),
        ("students", "0001_initial"),
        ("companies", "0001_initial"),
        ("placements", "0001_initial"),
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_groups, reverse_code=drop_groups),
    ]
