"""DRF serializers backing the ArticlesAndMore REST API (see views.py's
ArticleListCreateAPIView, SubscribedArticleListAPIView, and
ArticleDetailAPIView)."""
from rest_framework import serializers

from .models import Article, Newsletter, Publisher, User


class PublisherSerializer(serializers.ModelSerializer):
    """Read-only representation of a Publisher, used as a nested field
    on articles and newsletters."""

    class Meta:
        model = Publisher
        fields = ['id', 'name']


class UserSerializer(serializers.ModelSerializer):
    """Minimal, non-sensitive representation of a user for use as a nested
    field (e.g. an article's author). No password, email, or token data."""

    class Meta:
        model = User
        fields = ['id', 'username', 'role']
        read_only_fields = fields


class ArticleSerializer(serializers.ModelSerializer):
    """Full read/write representation of an Article for the REST API.

    author and publisher are returned as nested read-only objects;
    publisher_id accepts a raw Publisher pk on write. author, created_at,
    and approved can never be set or changed through this serializer.
    """

    author = UserSerializer(read_only=True)
    publisher = PublisherSerializer(read_only=True)

    # Accept a publisher id on write (POST/PUT) while still returning the
    # full nested object above on read. Optional: omit to publish
    # independently, matching ArticleForm's behaviour on the website.
    publisher_id = serializers.PrimaryKeyRelatedField(
        queryset=Publisher.objects.all(),
        source='publisher',
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'content', 'author',
            'publisher', 'publisher_id', 'created_at', 'approved',
        ]
        # author is always set from the authenticated user, never from the
        # request body; approved can only change via the editor-only
        # approval flow, not through this API.
        read_only_fields = ['id', 'author', 'created_at', 'approved']


class NewsletterSerializer(serializers.ModelSerializer):
    """Read-only representation of a Newsletter, including its nested
    author, publisher, and full list of articles."""

    author = UserSerializer(read_only=True)
    publisher = PublisherSerializer(read_only=True)
    articles = ArticleSerializer(many=True, read_only=True)

    class Meta:
        model = Newsletter
        fields = [
            'id', 'title', 'description', 'author',
            'publisher', 'articles', 'created_at',
        ]
        read_only_fields = fields