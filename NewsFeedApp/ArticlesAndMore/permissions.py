"""Maps each user role's Group name to the ArticlesAndMore permission
codenames it should hold. sync_role_groups (re)creates the Reader,
Journalist, and Editor groups with these permissions after every migrate.
sync_user_group keeps each User's group membership in sync with their
role whenever they're saved (e.g. on registration in AuthApp, or a role
change in the admin). Both are connected as signal receivers in
ArticlesAndMore/apps.py, so nothing outside this app needs to import
ROLE_PERMISSIONS directly.
"""

ROLE_PERMISSIONS = {
    'Reader': ['view_articles', 'view_newsletters'],
    'Journalist': [
        'view_articles', 'add_articles', 'change_articles', 'delete_articles',
        'view_newsletters', 'add_newsletters', 'change_newsletters', 'delete_newsletters',
    ],
    'Editor': [
        'view_articles', 'change_articles', 'delete_articles',
        'view_newsletters', 'change_newsletters', 'delete_newsletters',
    ],
}


def sync_role_groups(sender=None, **kwargs):
    """(Re)create the Reader, Journalist, and Editor groups with their
    permissions. Models are imported locally because this also runs as a
    post_migrate receiver, before the app registry is guaranteed ready.
    """
    from django.contrib.auth.models import Group, Permission

    for group_name, codenames in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        group.permissions.set(Permission.objects.filter(codename__in=codenames))


# Maps a User.role value to the Group name that grants its permissions.
ROLE_GROUP_NAMES = {
    'READER': 'Reader',
    'JOURNALIST': 'Journalist',
    'EDITOR': 'Editor',
}


def sync_user_group(sender, instance, **kwargs):
    """Whenever a User is saved, make sure they belong to exactly the
    Group matching their current role (and none of the other two role
    groups). Without this, a user's `role` field would drift out of sync
    with the actual Group-based permissions the app checks against.
    """
    from django.contrib.auth.models import Group

    target_group_name = ROLE_GROUP_NAMES.get(instance.role)
    role_groups = Group.objects.filter(name__in=ROLE_GROUP_NAMES.values())

    for group in role_groups:
        if group.name == target_group_name:
            instance.groups.add(group)
        else:
            instance.groups.remove(group)