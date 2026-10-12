"""App configuration for ArticlesAndMore."""
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ArticlesandmoreConfig(AppConfig):
    """Config for the ArticlesAndMore app; wires up the role/Group sync
    signal receivers defined in permissions.py."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ArticlesAndMore'

    def ready(self):
        """Connect the role/Group sync signal receivers once the app
        registry is ready."""
        from django.db.models.signals import post_save
        from .permissions import sync_role_groups, sync_user_group
        from .models import User

        # Groups + their permissions are (re)created after every migrate.
        post_migrate.connect(sync_role_groups, sender=self)

        # A user's Group membership is kept in sync with their role
        # every time they're saved (covers signup and any later role change).
        post_save.connect(sync_user_group, sender=User)