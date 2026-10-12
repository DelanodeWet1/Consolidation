"""Tests for the ArticlesAndMore app: the /api/articles/... REST API,
newsletter web views, and the article-approval notification side effects.

ArticleAPITestCase uses DRF's APITestCase, which spins up a real (in-memory,
per-test) database and lets us make requests through the same URL routing,
authentication, and permission machinery a real client would go through —
no mocking involved. Each test creates its own users/articles in setUp()
and every test runs in its own DB transaction that's rolled back afterwards,
so tests can't leak state into one another.

Test users are created with User.objects.create_user(...), which triggers
the post_save signal (sync_user_group, connected in apps.py) that puts them
in their role's Group. That Group's permissions are what has_perm() checks
against in _can_edit_article/_can_delete_article, and what makes 'editor1'
actually behave like an editor in these tests.

NewsletterViewTestCase and ArticleApprovalNotificationTestCase use plain
Django TestCase + the session-based test client, since newsletters and
article approval are HTML views, not part of the REST API.
"""
import json
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Article, Newsletter, Publisher, User


class ArticleAPITestCase(APITestCase):
    """Tests the /api/articles/... REST API endpoints, including the
    subscription-filtered /api/articles/subscribed/ endpoint.
    Each test runs in its own isolated database transaction."""
    def setUp(self):
        self.publisher = Publisher.objects.create(name='Test Publisher')

        self.reader = User.objects.create_user(
            username='reader1', password='testpass123', role=User.Role.READER,
        )
        self.journalist_a = User.objects.create_user(
            username='journalist_a', password='testpass123', role=User.Role.JOURNALIST,
        )
        self.journalist_b = User.objects.create_user(
            username='journalist_b', password='testpass123', role=User.Role.JOURNALIST,
        )
        self.editor = User.objects.create_user(
            username='editor1', password='testpass123', role=User.Role.EDITOR,
        )

        # The reader follows journalist_a directly, and separately follows
        # the publisher. journalist_b is followed by nobody.
        self.reader.journalist_subscriptions.add(self.journalist_a)
        self.reader.publisher_subscriptions.add(self.publisher)

        # Approved article by journalist_a, under the publisher the reader
        # follows -> should be visible to the reader two ways over.
        self.approved_article = Article.objects.create(
            title='Approved Article', content='Body text',
            author=self.journalist_a, publisher=self.publisher, approved=True,
        )
        # Same author, but not yet approved -> must stay invisible to the
        # reader regardless of the subscription above.
        self.unapproved_article = Article.objects.create(
            title='Unapproved Article', content='Body text',
            author=self.journalist_a, publisher=self.publisher, approved=False,
        )
        # Approved and independent (no publisher), but by journalist_b, who
        # the reader does NOT follow -> approved is not sufficient on its
        # own; this must stay invisible to the reader too.
        self.other_journalist_article = Article.objects.create(
            title="Journalist B's Article", content='Body text',
            author=self.journalist_b, publisher=None, approved=True,
        )

        self.reader_token = Token.objects.create(user=self.reader).key
        self.journalist_a_token = Token.objects.create(user=self.journalist_a).key
        self.journalist_b_token = Token.objects.create(user=self.journalist_b).key
        self.editor_token = Token.objects.create(user=self.editor).key

    def auth(self, token):
        """Attach a bearer token to every subsequent request made by
        self.client, the same way Postman's Authorization header would."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

    # ------------------------------------------------------------------
    # POST /api/token/
    # ------------------------------------------------------------------

    def test_obtain_token_with_valid_credentials(self):
        response = self.client.post(reverse('ArticlesAndMore:api_token'), {
            'username': 'reader1', 'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_obtain_token_with_invalid_credentials(self):
        response = self.client.post(reverse('ArticlesAndMore:api_token'), {
            'username': 'reader1', 'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Authentication is required at all, on every endpoint
    # ------------------------------------------------------------------

    def test_list_articles_requires_authentication(self):
        response = self.client.get(reverse('ArticlesAndMore:api_article_list_create'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token not-a-real-token')
        response = self.client.get(reverse('ArticlesAndMore:api_article_list_create'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ------------------------------------------------------------------
    # GET /api/articles/  -> every approved article, no subscription filter
    # ------------------------------------------------------------------

    def test_list_returns_only_approved_articles(self):
        self.auth(self.reader_token)
        response = self.client.get(reverse('ArticlesAndMore:api_article_list_create'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = {a['title'] for a in response.data}

        self.assertIn(self.approved_article.title, titles)
        # Approved but from an unsubscribed journalist: still shows up here,
        # because this endpoint is "all approved", not "my subscriptions".
        self.assertIn(self.other_journalist_article.title, titles)
        self.assertNotIn(self.unapproved_article.title, titles)

    # ------------------------------------------------------------------
    # GET /api/articles/subscribed/  -> approved AND subscribed, readers only
    # ------------------------------------------------------------------

    def test_subscribed_list_filters_by_subscription_and_approval(self):
        self.auth(self.reader_token)
        response = self.client.get(reverse('ArticlesAndMore:api_article_subscribed'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = {a['title'] for a in response.data}

        self.assertIn(self.approved_article.title, titles)
        self.assertNotIn(self.unapproved_article.title, titles)         # not approved
        self.assertNotIn(self.other_journalist_article.title, titles)   # not subscribed

    def test_subscribed_list_forbidden_for_non_readers(self):
        self.auth(self.journalist_a_token)
        response = self.client.get(reverse('ArticlesAndMore:api_article_subscribed'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------
    # GET /api/articles/<id>/
    # ------------------------------------------------------------------

    def test_retrieve_visible_article_as_reader(self):
        self.auth(self.reader_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.approved_article.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], self.approved_article.title)

    def test_retrieve_unapproved_article_as_reader_is_404(self):
        self.auth(self.reader_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.unapproved_article.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_unsubscribed_authors_article_as_reader_is_404(self):
        self.auth(self.reader_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.other_journalist_article.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_any_article_as_editor(self):
        self.auth(self.editor_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.unapproved_article.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # POST /api/articles/  -> journalists only, author always the caller
    # ------------------------------------------------------------------

    def test_create_article_as_journalist(self):
        self.auth(self.journalist_a_token)
        response = self.client.post(reverse('ArticlesAndMore:api_article_list_create'), {
            'title': 'New Article', 'content': 'Some content',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author']['username'], 'journalist_a')
        self.assertFalse(response.data['approved'])

    def test_create_article_ignores_client_supplied_author(self):
        self.auth(self.journalist_a_token)
        response = self.client.post(reverse('ArticlesAndMore:api_article_list_create'), {
            'title': 'Spoofed Author Attempt', 'content': 'x',
            'author': self.journalist_b.pk,  # should be silently ignored
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author']['username'], self.journalist_a.username)

    def test_create_article_forbidden_for_reader(self):
        self.auth(self.reader_token)
        response = self.client.post(reverse('ArticlesAndMore:api_article_list_create'), {
            'title': 'Should Fail', 'content': 'x',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_article_forbidden_for_editor(self):
        self.auth(self.editor_token)
        response = self.client.post(reverse('ArticlesAndMore:api_article_list_create'), {
            'title': 'Should Fail', 'content': 'x',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------
    # PUT /api/articles/<id>/  -> editors: any; journalists: own only
    # ------------------------------------------------------------------

    def test_update_own_article_as_journalist(self):
        self.auth(self.journalist_a_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.approved_article.pk])
        response = self.client.put(url, {'title': 'Updated Title', 'content': 'Updated body'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Title')

    def test_update_other_journalists_article_is_forbidden(self):
        self.auth(self.journalist_b_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.approved_article.pk])
        response = self.client.put(url, {'title': 'Hijacked', 'content': 'x'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.approved_article.refresh_from_db()
        self.assertNotEqual(self.approved_article.title, 'Hijacked')

    def test_update_any_article_as_editor(self):
        self.auth(self.editor_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.approved_article.pk])
        response = self.client.put(url, {'title': 'Editor Edit', 'content': 'x'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_cannot_change_approved_field(self):
        self.auth(self.journalist_a_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.unapproved_article.pk])
        response = self.client.put(url, {
            'title': 'Still Unapproved', 'content': 'x', 'approved': True,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['approved'])
        self.unapproved_article.refresh_from_db()
        self.assertFalse(self.unapproved_article.approved)

    def test_patch_is_not_allowed(self):
        self.auth(self.journalist_a_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.approved_article.pk])
        response = self.client.patch(url, {'title': 'Partial Update'})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ------------------------------------------------------------------
    # DELETE /api/articles/<id>/  -> editors: any; journalists: own only
    # ------------------------------------------------------------------

    def test_delete_own_article_as_journalist(self):
        self.auth(self.journalist_a_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.unapproved_article.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Article.objects.filter(pk=self.unapproved_article.pk).exists())

    def test_delete_other_journalists_article_is_forbidden(self):
        self.auth(self.journalist_b_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.approved_article.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Article.objects.filter(pk=self.approved_article.pk).exists())

    def test_delete_any_article_as_editor(self):
        self.auth(self.editor_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.unapproved_article.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_forbidden_for_reader(self):
        self.auth(self.reader_token)
        url = reverse('ArticlesAndMore:api_article_detail', args=[self.approved_article.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Article.objects.filter(pk=self.approved_article.pk).exists())


class NewsletterViewTestCase(TestCase):
    """Newsletter creation, editing, and reader visibility via the regular
    (session-authenticated) HTML views, not the REST API — there's no
    /api/newsletters/... endpoint, so these go through self.client as a
    logged-in browser session would."""

    def setUp(self):
        self.publisher = Publisher.objects.create(name='Test Publisher')

        self.reader = User.objects.create_user(
            username='reader1', password='testpass123', role=User.Role.READER,
        )
        self.journalist_a = User.objects.create_user(
            username='journalist_a', password='testpass123', role=User.Role.JOURNALIST,
        )
        self.journalist_b = User.objects.create_user(
            username='journalist_b', password='testpass123', role=User.Role.JOURNALIST,
        )
        self.editor = User.objects.create_user(
            username='editor1', password='testpass123', role=User.Role.EDITOR,
        )

        # The reader follows journalist_a only.
        self.reader.journalist_subscriptions.add(self.journalist_a)

        self.article = Article.objects.create(
            title='Featured Article', content='Body text',
            author=self.journalist_a, publisher=self.publisher, approved=True,
        )

        # Independent newsletter (no publisher) by journalist_a -> visible
        # to the reader via the journalist_subscriptions match.
        self.newsletter = Newsletter.objects.create(
            title="Journalist A's Newsletter", description='A weekly roundup',
            author=self.journalist_a, publisher=None,
        )
        self.newsletter.articles.add(self.article)

        # By journalist_b, who the reader does not follow -> must stay
        # invisible to the reader.
        self.other_newsletter = Newsletter.objects.create(
            title="Journalist B's Newsletter", description='Unrelated',
            author=self.journalist_b, publisher=None,
        )

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def test_journalist_can_create_newsletter(self):
        self.client.login(username='journalist_a', password='testpass123')
        response = self.client.post(reverse('ArticlesAndMore:newsletter_create'), {
            'title': 'New Newsletter', 'description': 'A new one',
            'articles': [self.article.pk],
        })
        newsletter = Newsletter.objects.get(title='New Newsletter')
        self.assertRedirects(
            response, reverse('ArticlesAndMore:newsletter_detail', args=[newsletter.pk])
        )
        self.assertEqual(newsletter.author, self.journalist_a)

    def test_reader_cannot_create_newsletter(self):
        self.client.login(username='reader1', password='testpass123')
        self.client.post(reverse('ArticlesAndMore:newsletter_create'), {
            'title': 'Should Fail', 'description': 'x', 'articles': [self.article.pk],
        })
        self.assertFalse(Newsletter.objects.filter(title='Should Fail').exists())

    def test_editor_cannot_create_newsletter(self):
        # add_newsletters is a Journalist-only permission (see ROLE_PERMISSIONS
        # in permissions.py) — editors can change/delete but not create.
        self.client.login(username='editor1', password='testpass123')
        self.client.post(reverse('ArticlesAndMore:newsletter_create'), {
            'title': 'Should Fail', 'description': 'x', 'articles': [self.article.pk],
        })
        self.assertFalse(Newsletter.objects.filter(title='Should Fail').exists())

    # ------------------------------------------------------------------
    # Editing — no ownership restriction for newsletters (unlike articles):
    # any Journalist or Editor with the relevant permission can edit any
    # newsletter.
    # ------------------------------------------------------------------

    def test_journalist_can_edit_any_newsletter(self):
        self.client.login(username='journalist_b', password='testpass123')
        self.client.post(
            reverse('ArticlesAndMore:newsletter_update', args=[self.newsletter.pk]),
            {'title': 'Edited by B', 'description': 'desc', 'articles': [self.article.pk]},
        )
        self.newsletter.refresh_from_db()
        self.assertEqual(self.newsletter.title, 'Edited by B')

    def test_editor_can_edit_any_newsletter(self):
        self.client.login(username='editor1', password='testpass123')
        self.client.post(
            reverse('ArticlesAndMore:newsletter_update', args=[self.newsletter.pk]),
            {'title': 'Edited by editor', 'description': 'desc', 'articles': [self.article.pk]},
        )
        self.newsletter.refresh_from_db()
        self.assertEqual(self.newsletter.title, 'Edited by editor')

    def test_reader_cannot_edit_newsletter(self):
        self.client.login(username='reader1', password='testpass123')
        self.client.post(
            reverse('ArticlesAndMore:newsletter_update', args=[self.newsletter.pk]),
            {'title': 'Should Not Apply', 'description': 'desc', 'articles': [self.article.pk]},
        )
        self.newsletter.refresh_from_db()
        self.assertNotEqual(self.newsletter.title, 'Should Not Apply')

    # ------------------------------------------------------------------
    # Viewing — list and detail both apply the subscription rule for
    # readers; journalists/editors see everything.
    # ------------------------------------------------------------------

    def test_reader_sees_only_subscribed_newsletters_in_list(self):
        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(reverse('ArticlesAndMore:newsletter_list'))
        newsletters = list(response.context['newsletters'])
        self.assertIn(self.newsletter, newsletters)
        self.assertNotIn(self.other_newsletter, newsletters)

    def test_journalist_sees_all_newsletters_in_list(self):
        self.client.login(username='journalist_a', password='testpass123')
        response = self.client.get(reverse('ArticlesAndMore:newsletter_list'))
        newsletters = list(response.context['newsletters'])
        self.assertIn(self.newsletter, newsletters)
        self.assertIn(self.other_newsletter, newsletters)

    def test_reader_can_view_subscribed_newsletter_detail(self):
        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(
            reverse('ArticlesAndMore:newsletter_detail', args=[self.newsletter.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['newsletter'], self.newsletter)

    def test_reader_cannot_view_unsubscribed_newsletter_detail(self):
        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(
            reverse('ArticlesAndMore:newsletter_detail', args=[self.other_newsletter.pk])
        )
        # Redirected (server-side render) to newsletter_list with an error,
        # rather than leaking the restricted newsletter's content.
        self.assertNotIn('newsletter', response.context)
        self.assertContains(response, 'You do not have permission')

    def test_newsletter_detail_hides_unapproved_articles_from_reader(self):
        unapproved = Article.objects.create(
            title='Unapproved', content='x', author=self.journalist_a,
            publisher=self.publisher, approved=False,
        )
        self.newsletter.articles.add(unapproved)

        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(
            reverse('ArticlesAndMore:newsletter_detail', args=[self.newsletter.pk])
        )
        articles_shown = list(response.context['articles'])
        self.assertIn(self.article, articles_shown)
        self.assertNotIn(unapproved, articles_shown)

    def test_journalist_sees_unapproved_articles_in_newsletter(self):
        unapproved = Article.objects.create(
            title='Unapproved2', content='x', author=self.journalist_a,
            publisher=self.publisher, approved=False,
        )
        self.newsletter.articles.add(unapproved)

        self.client.login(username='journalist_a', password='testpass123')
        response = self.client.get(
            reverse('ArticlesAndMore:newsletter_detail', args=[self.newsletter.pk])
        )
        articles_shown = list(response.context['articles'])
        self.assertIn(unapproved, articles_shown)


class ArticleApprovalNotificationTestCase(TestCase):
    """Verifies that approving an article — the not-approved -> approved
    transition inside article_approve — triggers both approval side
    effects: the subscriber email and the POST to /api/approved/. The
    external POST is always mocked, since letting it run for real would
    mean the Django test client (which isn't a real listening server)
    attempting a genuine network connection on every approval. The email
    doesn't strictly need mocking (Django's test runner already swaps in
    an in-memory backend automatically) but mocking notify_article_approved
    directly is the simplest way to confirm article_approve calls it at
    all, independent of what it does internally.
    """

    def setUp(self):
        self.publisher = Publisher.objects.create(name='Test Publisher')

        self.reader = User.objects.create_user(
            username='reader1', password='testpass123', role=User.Role.READER,
            email='reader1@example.com',
        )
        self.journalist = User.objects.create_user(
            username='journalist_a', password='testpass123', role=User.Role.JOURNALIST,
        )
        self.editor = User.objects.create_user(
            username='editor1', password='testpass123', role=User.Role.EDITOR,
        )

        self.reader.journalist_subscriptions.add(self.journalist)

        self.article = Article.objects.create(
            title='Breaking News', content='Body text',
            author=self.journalist, publisher=self.publisher, approved=False,
        )

    @patch('ArticlesAndMore.views.notify_article_approved')
    def test_approving_article_triggers_notification(self, mock_notify):
        self.client.login(username='editor1', password='testpass123')
        self.client.get(reverse('ArticlesAndMore:article_approve', args=[self.article.pk]))
        self.article.refresh_from_db()

        self.assertTrue(self.article.approved)
        mock_notify.assert_called_once()
        notified_article = mock_notify.call_args[0][0]
        self.assertEqual(notified_article.pk, self.article.pk)

    @patch('ArticlesAndMore.views.notify_article_approved')
    def test_unapproving_article_does_not_trigger_notification(self, mock_notify):
        self.article.approved = True
        self.article.save()

        self.client.login(username='editor1', password='testpass123')
        self.client.get(reverse('ArticlesAndMore:article_approve', args=[self.article.pk]))
        self.article.refresh_from_db()

        self.assertFalse(self.article.approved)
        mock_notify.assert_not_called()

    @patch('ArticlesAndMore.notifications.urllib_request.urlopen')
    def test_approving_article_sends_email_to_subscribers(self, mock_urlopen):
        # Only the network call is mocked here — notify_article_approved
        # runs for real, so this exercises the actual email-building logic
        # via Django's locmem test email backend (mail.outbox).
        self.client.login(username='editor1', password='testpass123')
        self.client.get(reverse('ArticlesAndMore:article_approve', args=[self.article.pk]))

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn(self.reader.email, sent.to)
        self.assertIn(self.article.title, sent.subject)

    @patch('ArticlesAndMore.notifications.urllib_request.urlopen')
    def test_approving_article_posts_to_external_api(self, mock_urlopen):
        self.client.login(username='editor1', password='testpass123')
        self.client.get(reverse('ArticlesAndMore:article_approve', args=[self.article.pk]))

        mock_urlopen.assert_called_once()
        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith('/api/approved/'))
        self.assertEqual(sent_request.get_method(), 'POST')

        payload = json.loads(sent_request.data)
        self.assertEqual(payload['id'], self.article.pk)
        self.assertEqual(payload['title'], self.article.title)
