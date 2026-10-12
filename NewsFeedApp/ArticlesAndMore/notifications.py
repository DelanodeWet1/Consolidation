"""Notification side-effects that fire when an editor approves an article:

1. Email every reader subscribed to the article's author or its publisher.
2. POST the article to this project's own /api/approved endpoint, standing
   in for a real third-party integration while keeping everything local.

Both are called from views.article_approve, right after an article
transitions from not-approved to approved.
"""
import json
import logging
from urllib import request as urllib_request
from urllib.error import URLError

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.urls import reverse

logger = logging.getLogger(__name__)


def _recipient_emails(article):
    """Email addresses of every reader subscribed to this article's author
    or its publisher."""
    from .models import User  # local import avoids a circular import at module load time

    conditions = Q(pk__in=[])
    if article.author_id:
        conditions |= Q(journalist_subscriptions=article.author_id)
    if article.publisher_id:
        conditions |= Q(publisher_subscriptions=article.publisher_id)

    readers = (
        User.objects.filter(role=User.Role.READER)
        .filter(conditions)
        .exclude(email='')
        .distinct()
    )
    return list(readers.values_list('email', flat=True))


def send_approval_email(article):
    """Email every subscribed reader that this article has been approved."""
    recipients = _recipient_emails(article)
    if not recipients:
        return

    subject = f"New article published: {article.title}"
    body = (
        f"{article.title}\n\n"
        f"{article.content}\n\n"
        f"By {article.author}"
        + (f", published by {article.publisher}" if article.publisher_id else " (independent)")
    )

    send_mail(
        subject,
        body,
        settings.EMAIL_HOST_USER,
        recipients,
        fail_silently=False,
    )


def share_article_externally(article, request):
    """POST the approved article to this project's own /api/approved
    endpoint.
    """
    url = request.build_absolute_uri(reverse('ArticlesAndMore:api_approved'))
    payload = json.dumps({
        'id': article.pk,
        'title': article.title,
        'content': article.content,
        'author': article.author.username if article.author_id else None,
        'publisher': article.publisher.name if article.publisher_id else None,
        'created_at': article.created_at.isoformat(),
    }).encode('utf-8')

    req = urllib_request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib_request.urlopen(req, timeout=5) as response:
            response.read()
    except URLError:
        logger.exception('Failed to POST approved article %s to %s', article.pk, url)


def notify_article_approved(article, request):
    """Run both approval side-effects. Called once, right after an article
    transitions from not-approved to approved."""
    send_approval_email(article)
    share_article_externally(article, request)
