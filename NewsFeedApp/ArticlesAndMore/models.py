from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser


class Article(models.Model):
    """Article model representing a news article in the system."""
    title = models.CharField(max_length=100)
    # title of the article

    content = models.TextField(blank=True)
    # the body of the article
    
    # The journalist who wrote the article
    author = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.CASCADE, related_name='articles', null=True, blank=True
        )
    
    # Foreign key for the publisher
    publisher = models.ForeignKey(
            "Publisher",
            on_delete=models.CASCADE, related_name='articles', null=True, blank=True
        )

    # Date at which the article was added to the database
    created_at = models.DateTimeField(auto_now_add=True)

    # Boolean showing whether the article has been approved by an editor or not
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    class Meta:
        # These are special permissions for users who can add, change, delete, or view articles
        permissions = [
            ("add_articles", "Can add articles"),
            ("change_articles", "Can change articles"),
            ("delete_articles", "Can delete articles"),
            ("view_articles", "Can view articles"),
        ]


class Publisher(models.Model):
    """Publisher model representing a news publisher in the system."""
    name = models.CharField(max_length=100)
    # name of the publisher
    
    def __str__(self):
        return self.name


class Newsletter(models.Model):
    """Newsletter model representing a news newsletter in the system."""
    title = models.CharField(max_length=100)
    # title of the newsletter

    # The description of the newsletter
    description = models.TextField(blank=True)
    
    # foreign key defining the many to many relationship with articles
    articles = models.ManyToManyField('Article', related_name='newsletters')
    
    # Foreign key defining the publisher relationship
    publisher = models.ForeignKey(
                'Publisher',
                on_delete=models.CASCADE, related_name='newsletters', null=True, blank=True
            )
    
    # The journalist who created the newsletter
    author = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.CASCADE, related_name='newsletters', null=True, blank=True
        )

    # Date at which the newsletter was added to the database
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        # These are special permissions for users who can add, change, delete, or view articles
        permissions = [
            ("add_newsletters", "Can add newsletters"),
            ("change_newsletters", "Can change newsletters"),
            ("delete_newsletters", "Can delete newsletters"),
            ("view_newsletters", "Can view newsletters"),
        ]
        

class User(AbstractUser):
    """Custom user model extending Django's AbstractUser to include roles and relationships with publishers and subscriptions."""
    class Role(models.TextChoices):
        READER = 'READER', 'Reader'
        JOURNALIST = 'JOURNALIST', 'Journalist'
        EDITOR = 'EDITOR', 'Editor'

    role = models.CharField(max_length=20, choices=Role.choices)
    
    # Defines the one-to-many relationship between a publisher and its journalists
    # (one publisher can have many journalists; each journalist works for one publisher)
    publisher_j = models.ForeignKey(
        'Publisher',
        on_delete=models.SET_NULL,
        related_name='journalists',
        null=True,
        blank=True
    )

    # Defines the one-to-many relationship between a publisher and its editors
    # (one publisher can have many editors; each editor can work for several publishers)
    publisher_e = models.ManyToManyField(
        'Publisher',
        related_name='editors',
        blank=True
    )
    
    # Defines the many-to-many relationship for reader subscriptions to publishers
    publisher_subscriptions = models.ManyToManyField(
            'Publisher',
            related_name='subscribers',
            blank=True
        )
    # Defines the many-to-many relationship for reader subscriptions to journalists
    journalist_subscriptions = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='subscribers',
        blank=True
    )
    

    def clean(self):
        super().clean()
        if self.role != self.Role.JOURNALIST and self.publisher_j:
            raise ValidationError(
                "Only journalists can be assigned to a publisher as a journalist."
            )

        if self.role != self.Role.EDITOR and self.publisher_e.exists():
            raise ValidationError(
                "Only editors can be assigned to a publisher as an editor."
            )
        
        if self.role != self.Role.READER and self.pk and self.journalist_subscriptions.exists():
            raise ValidationError(
                "Only readers can subscribe to journalists."
            )
            
        if self.role != self.Role.READER and self.pk and self.publisher_subscriptions.exists():
            raise ValidationError(
                "Only readers can subscribe to publishers."
            )

    def save(self, *args, **kwargs):
        """Enforce that a user only ever holds the fields relevant to their
        current role. clean() rejects an invalid combination when a form
        calls full_clean() first, but nothing previously stopped a direct
        .save() (e.g. an admin edit, a script, a role change elsewhere in
        the app) from leaving stale data on the "wrong" fields for the new
        role. This clears them unconditionally on every save, so the
        model's own persistence layer guarantees the invariant regardless
        of how it's saved: a Journalist's publisher_e is always None, an
        Editor's publisher_j is always None, and neither has reader
        subscriptions — and vice versa, a Reader has neither publisher_j
        nor publisher_e set.
        """
        # M2M relations can't be touched before the instance has a pk, so
        # capture "is this a brand-new row" before super().save() assigns
        # one. A new user can't have subscriptions yet regardless, so this
        # only matters when an existing user's role changes later.
        is_new = self._state.adding

        super().save(*args, **kwargs)

        if self.role != self.Role.JOURNALIST:
            self.publisher_j = None
        if self.role != self.Role.EDITOR:
            self.publisher_e.clear()
        if self.role != self.Role.READER and not is_new:
            self.journalist_subscriptions.clear()
            self.publisher_subscriptions.clear()

    @property
    def independent_articles(self):
        """This journalist's articles published without going through a
        publisher (publisher is None) — explicitly exposed since it's a
        distinct, meaningful subset of user.articles.all()."""
        return self.articles.filter(publisher__isnull=True)

    @property
    def independent_newsletters(self):
        """This journalist's newsletters published without going through a
        publisher (publisher is None), for the same reason as above."""
        return self.newsletters.filter(publisher__isnull=True)