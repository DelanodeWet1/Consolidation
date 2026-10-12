import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound, PermissionDenied

from .forms import ArticleForm, AssignJournalistForm, NewsletterForm, PublisherForm
from .models import Article, Newsletter, Publisher, User
from .notifications import notify_article_approved
from .serializers import ArticleSerializer

logger = logging.getLogger(__name__)


def _visible_to_reader(queryset, user):
    """Filter a queryset to items whose publisher or author the given
    reader is subscribed to (either match is sufficient)."""
    return queryset.filter(
        Q(publisher__in=user.publisher_subscriptions.all())
        | Q(author__in=user.journalist_subscriptions.all())
    )


def _can_edit_article(user, article):
    """Editors can edit any article; journalists can only edit their own."""
    if user.role == User.Role.EDITOR:
        return user.has_perm('ArticlesAndMore.change_articles') and (article.publisher in user.publisher_e.all() or article.publisher is None)
    return user.has_perm('ArticlesAndMore.change_articles') and user == article.author


def _can_delete_article(user, article):
    """Editors can delete any article; journalists can only delete their own."""
    if user.role == User.Role.EDITOR:
        return user.has_perm('ArticlesAndMore.delete_articles') and (article.publisher in user.publisher_e.all() or article.publisher is None)
    return user.has_perm('ArticlesAndMore.delete_articles') and user == article.author

def _can_approve_article(user, article):
    """Editors can approve articles that are independent or belong to their publisher."""
    if user.role == User.Role.EDITOR:
        return article.publisher in user.publisher_e.all() or article.publisher is None
    return False

@login_required(login_url=reverse_lazy('AuthApp:login'))
def article_list(request):
    """List articles. Readers see only approved articles from publishers or
    journalists they follow; journalists and editors see everything."""
    user = request.user
    articles = Article.objects.all().order_by('-created_at')
    if user.role == User.Role.READER:
        articles = _visible_to_reader(articles.filter(approved=True), user)
    if user.role == User.Role.JOURNALIST:
        articles = articles.filter(author=user)
    return render(request, 'ArticlesAndMore/article_list.html', {'articles': articles})


@login_required(login_url=reverse_lazy('AuthApp:login'))
def article_detail(request, pk):
    """Show a single article. Readers may only view approved articles from
    a publisher or journalist they're subscribed to (same rule as
    article_list); journalists and editors can view any article."""
    user = request.user
    article = get_object_or_404(Article, pk=pk)

    if user.role == User.Role.READER:
        visible = _visible_to_reader(
            Article.objects.filter(pk=article.pk, approved=True), user
        )
        if not visible.exists():
            visible_articles = _visible_to_reader(
                Article.objects.filter(approved=True), user
            ).order_by('-created_at')
            return render(request, 'ArticlesAndMore/article_list.html', {
                'articles': visible_articles,
                'error': 'You do not have permission to view this article.',
            })

    return render(request, 'ArticlesAndMore/article_detail.html', {
        'article': article,
        'can_edit': _can_edit_article(user, article),
        'can_delete': _can_delete_article(user, article),
        'can_approve': _can_approve_article(user, article),
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def article_create(request):
    """Create an article. Journalists may select any publisher, or leave
    it unset to publish independently."""
    user = request.user

    if not user.has_perm('ArticlesAndMore.add_articles'):
        return render(request, 'ArticlesAndMore/article_list.html', {
            'articles': Article.objects.all().order_by('-created_at'),
            'error': 'You do not have permission to create articles.',
        })

    if request.method == 'POST':
        form = ArticleForm(request.POST)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = user
            article.save()
            return redirect('ArticlesAndMore:article_detail', pk=article.pk)
    else:
        form = ArticleForm()

    return render(request, 'ArticlesAndMore/article_form.html', {'form': form})


@login_required(login_url=reverse_lazy('AuthApp:login'))
def article_update(request, pk):
    """Update an article. Editors may update any article; journalists may
    only update articles they wrote themselves."""
    user = request.user
    article = get_object_or_404(Article, pk=pk)

    if _can_edit_article(user, article):
        if request.method == 'POST':
            form = ArticleForm(request.POST, instance=article)
            if form.is_valid():
                form.save()
                return redirect('ArticlesAndMore:article_detail', pk=article.pk)
        else:
            form = ArticleForm(instance=article)
        return render(request, 'ArticlesAndMore/article_form.html', {'form': form})

    return render(request, 'ArticlesAndMore/article_detail.html', {
        'article': article,
        'error': 'You do not have permission to update this article.',
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def article_delete(request, pk):
    """Delete an article. Editors may delete any article; journalists may
    only delete articles they wrote themselves."""
    user = request.user
    article = get_object_or_404(Article, pk=pk)

    if _can_delete_article(user, article):
        article.delete()
        return redirect('ArticlesAndMore:article_list')

    return render(request, 'ArticlesAndMore/article_detail.html', {
        'article': article,
        'error': 'You do not have permission to delete this article.',
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def article_approve(request, pk):
    """Toggle an article's approved status. Editors only. When an article
    is newly approved (not when it's unapproved), notify subscribers by
    email and share it via the internal /api/approved endpoint."""
    user = request.user
    article = get_object_or_404(Article, pk=pk)

    if _can_approve_article(user, article):
        article.approved = not article.approved
        article.save()
        if article.approved:
            notify_article_approved(article, request)
        return redirect('ArticlesAndMore:article_detail', pk=article.pk)

    return render(request, 'ArticlesAndMore/article_detail.html', {
        'article': article,
        'error': 'You do not have permission to approve articles.',
    })


@csrf_exempt
@require_POST
def api_approved(request):
    """Stands in for a third-party 'article received' endpoint. Real
    external integrations wouldn't hold a Django session or CSRF token,
    so this view is intentionally exempt from CSRF and open to any POST —
    logs whatever payload it receives and echoes it back."""
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON body.')

    logger.info('Received approved article via /api/approved: %s', payload)
    return JsonResponse({'status': 'received', 'article': payload})


@login_required(login_url=reverse_lazy('AuthApp:login'))
def newsletter_list(request):
    """List newsletters. Readers see only newsletters from publishers or
    journalists they follow; journalists and editors see everything."""
    user = request.user
    newsletters = Newsletter.objects.all().order_by('-created_at')
    if user.role == User.Role.READER:
        newsletters = _visible_to_reader(newsletters, user)
    if user.role == User.Role.JOURNALIST:
        newsletters = newsletters.filter(author=user)
    return render(request, 'ArticlesAndMore/newsletter_list.html', {'newsletters': newsletters})


@login_required(login_url=reverse_lazy('AuthApp:login'))
def newsletter_detail(request, pk):
    """Show a single newsletter. Readers may only view newsletters from a
    publisher or journalist they're subscribed to (same rule as
    newsletter_list); journalists and editors can view any newsletter.
    Within the newsletter, readers only see its approved articles."""
    user = request.user
    newsletter = get_object_or_404(Newsletter, pk=pk)

    if user.role == User.Role.READER:
        visible = _visible_to_reader(Newsletter.objects.filter(pk=newsletter.pk), user)
        if not visible.exists():
            visible_newsletters = _visible_to_reader(
                Newsletter.objects.all(), user
            ).order_by('-created_at')
            return render(request, 'ArticlesAndMore/newsletter_list.html', {
                'newsletters': visible_newsletters,
                'error': 'You do not have permission to view this newsletter.',
            })

    articles = newsletter.articles.all().order_by('-created_at')
    if user.role == User.Role.READER:
        articles = articles.filter(approved=True)
    return render(request, 'ArticlesAndMore/newsletter_detail.html', {
        'newsletter': newsletter,
        'articles': articles,
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def newsletter_create(request):
    """Create a newsletter. Only approved articles can be added to a newsletter.
    Journalists may select any publisher, or leave it unset to publish independently."""
    user = request.user

    if not user.has_perm('ArticlesAndMore.add_newsletters'):
        return render(request, 'ArticlesAndMore/newsletter_list.html', {
            'newsletters': Newsletter.objects.all().order_by('-created_at'),
            'error': 'You do not have permission to create newsletters.',
        })

    if request.method == 'POST':
        form = NewsletterForm(request.POST)
        if form.is_valid():
            newsletter = form.save(commit=False)
            newsletter.author = user
            newsletter.save()
            form.save_m2m()  # persist the 'articles' M2M selections
            return redirect('ArticlesAndMore:newsletter_detail', pk=newsletter.pk)
    else:
        form = NewsletterForm()

    return render(request, 'ArticlesAndMore/newsletter_form.html', {'form': form})


@login_required(login_url=reverse_lazy('AuthApp:login'))
def newsletter_update(request, pk):
    """Update a newsletter. Restricted to users with the change_newsletters
    permission (Journalists and Editors)."""
    user = request.user
    newsletter = get_object_or_404(Newsletter, pk=pk)

    if user.has_perm('ArticlesAndMore.change_newsletters'):
        if request.method == 'POST':
            form = NewsletterForm(request.POST, instance=newsletter)
            if form.is_valid():
                form.save()
                return redirect('ArticlesAndMore:newsletter_detail', pk=newsletter.pk)
        else:
            form = NewsletterForm(instance=newsletter)
        return render(request, 'ArticlesAndMore/newsletter_form.html', {'form': form})

    return render(request, 'ArticlesAndMore/newsletter_detail.html', {
        'newsletter': newsletter,
        'error': 'You do not have permission to update this newsletter.',
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def newsletter_delete(request, pk):
    """Delete a newsletter. Restricted to users with the delete_newsletters
    permission (Journalists and Editors)."""
    user = request.user
    newsletter = get_object_or_404(Newsletter, pk=pk)

    if user.has_perm('ArticlesAndMore.delete_newsletters'):
        newsletter.delete()
        return redirect('ArticlesAndMore:newsletter_list')

    return render(request, 'ArticlesAndMore/newsletter_detail.html', {
        'newsletter': newsletter,
        'error': 'You do not have permission to delete this newsletter.',
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def publisher_list(request):
    """List all publishers. Readers can subscribe/unsubscribe from here."""
    user = request.user
    publishers = Publisher.objects.all().order_by('name')
    subscribed_ids = set()
    if user.role == User.Role.READER:
        subscribed_ids = set(user.publisher_subscriptions.values_list('pk', flat=True))
    return render(request, 'ArticlesAndMore/publisher_list.html', {
        'publishers': publishers,
        'subscribed_ids': subscribed_ids,
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def publisher_create(request):
    """Create a new publisher. Restricted to editors who aren't already
    assigned to one — creating a publisher automatically assigns the
    creating editor to it, and publisher_e is a single field, so an editor
    can only belong to one publisher at a time."""
    user = request.user

    if user.role != User.Role.EDITOR:
        return render(request, 'ArticlesAndMore/publisher_list.html', {
            'publishers': Publisher.objects.all().order_by('name'),
            'error': 'Only editors can create publishers.',
        })

    if request.method == 'POST':
        form = PublisherForm(request.POST)
        if form.is_valid():
            publisher = form.save()
            if user.publisher_e is None:
                user.publisher_e.set(publisher)
            else:
                user.publisher_e.add(publisher)
            user.save()
            return redirect('ArticlesAndMore:publisher_detail', pk=publisher.pk)
    else:
        form = PublisherForm()

    return render(request, 'ArticlesAndMore/publisher_form.html', {'form': form})


@login_required(login_url=reverse_lazy('AuthApp:login'))
def publisher_detail(request, pk):
    """Show a single publisher: its editors, journalists, and articles.
    Readers can subscribe/unsubscribe here; an unassigned editor can join;
    the publisher's own editor(s) can manage its journalists or leave."""
    user = request.user
    publisher = get_object_or_404(Publisher, pk=pk)

    is_subscribed = (
        user.role == User.Role.READER
        and publisher in user.publisher_subscriptions.all()
    )
    can_manage_staff = user.role == User.Role.EDITOR and publisher in user.publisher_e.all()

    return render(request, 'ArticlesAndMore/publisher_detail.html', {
        'publisher': publisher,
        'is_subscribed': is_subscribed,
        'can_join': user.role == User.Role.EDITOR,
        'can_manage_staff': can_manage_staff,
        'can_leave': can_manage_staff,
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def toggle_publisher_subscription(request, pk):
    """Subscribe/unsubscribe the current reader to a publisher."""
    user = request.user
    publisher = get_object_or_404(Publisher, pk=pk)

    if user.role == User.Role.READER:
        if publisher in user.publisher_subscriptions.all():
            user.publisher_subscriptions.remove(publisher)
        else:
            user.publisher_subscriptions.add(publisher)
        return redirect('ArticlesAndMore:publisher_list')

    return render(request, 'ArticlesAndMore/publisher_list.html', {
        'publishers': Publisher.objects.all().order_by('name'),
        'error': 'Only readers can subscribe to publishers.',
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def publisher_assign_self(request, pk):
    """An unassigned editor joins an existing publisher as one of its
    editors. Multiple editors can share the same publisher — publisher_e
    is many-to-many."""
    user = request.user
    publisher = get_object_or_404(Publisher, pk=pk)

    if user.role == User.Role.EDITOR:
        if user.publisher_e is None:
            user.publisher_e.set(publisher)
        else:
            user.publisher_e.add(publisher)
        user.save()
        return redirect('ArticlesAndMore:publisher_detail', pk=publisher.pk)

    return render(request, 'ArticlesAndMore/publisher_detail.html', {
        'publisher': publisher,
        'error': 'You are not able to join this publisher.',
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def publisher_leave(request, pk):
    """An editor leaves the publisher they're currently assigned to."""
    user = request.user
    publisher = get_object_or_404(Publisher, pk=pk)

    if user.role == User.Role.EDITOR and publisher in user.publisher_e.all():
        user.publisher_e.remove(publisher)
        user.save()
        return redirect('ArticlesAndMore:publisher_detail', pk=publisher.pk)

    return render(request, 'ArticlesAndMore/publisher_detail.html', {
        'publisher': publisher,
        'error': 'You are not assigned to this publisher.',
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def publisher_assign_journalist(request, pk):
    """The publisher's own editor assigns an unassigned journalist to it.
    GET shows a form with a dropdown of journalists with no publisher yet
    (see AssignJournalistForm); POST assigns the selected one."""
    user = request.user
    publisher = get_object_or_404(Publisher, pk=pk)

    if not (user.role == User.Role.EDITOR and publisher in user.publisher_e.all()):
        return render(request, 'ArticlesAndMore/publisher_detail.html', {
            'publisher': publisher,
            'error': "You do not have permission to manage this publisher's staff.",
        })

    if request.method == 'POST':
        form = AssignJournalistForm(request.POST)
        if form.is_valid():
            journalist = form.cleaned_data['journalist']
            journalist.publisher_j = publisher
            journalist.save()
            return redirect('ArticlesAndMore:publisher_detail', pk=publisher.pk)
    else:
        form = AssignJournalistForm()

    return render(request, 'ArticlesAndMore/publisher_assign_journalist.html', {
        'publisher': publisher,
        'form': form,
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def publisher_remove_journalist(request, pk, journalist_id):
    """The publisher's own editor removes one of its journalists, freeing
    that journalist up to be assigned elsewhere."""
    user = request.user
    publisher = get_object_or_404(Publisher, pk=pk)
    journalist = get_object_or_404(User, pk=journalist_id, role=User.Role.JOURNALIST)

    is_own_publisher = user.role == User.Role.EDITOR and publisher in user.publisher_e.all()
    if is_own_publisher and journalist.publisher_j == publisher:
        journalist.publisher_j = None
        journalist.save()
        return redirect('ArticlesAndMore:publisher_detail', pk=publisher.pk)

    return render(request, 'ArticlesAndMore/publisher_detail.html', {
        'publisher': publisher,
        'error': 'You do not have permission to remove this journalist.',
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def journalist_list(request):
    """List all journalists. Readers can subscribe/unsubscribe from here."""
    user = request.user
    journalists = User.objects.filter(role=User.Role.JOURNALIST).order_by('username')
    subscribed_ids = set()
    if user.role == User.Role.READER:
        subscribed_ids = set(user.journalist_subscriptions.values_list('pk', flat=True))
    return render(request, 'ArticlesAndMore/journalist_list.html', {
        'journalists': journalists,
        'subscribed_ids': subscribed_ids,
    })


@login_required(login_url=reverse_lazy('AuthApp:login'))
def toggle_journalist_subscription(request, pk):
    """Subscribe/unsubscribe the current reader to a journalist."""
    user = request.user
    journalist = get_object_or_404(User, pk=pk, role=User.Role.JOURNALIST)

    if user.role == User.Role.READER:
        if journalist in user.journalist_subscriptions.all():
            user.journalist_subscriptions.remove(journalist)
        else:
            user.journalist_subscriptions.add(journalist)
        return redirect('ArticlesAndMore:journalist_list')

    return render(request, 'ArticlesAndMore/journalist_list.html', {
        'journalists': User.objects.filter(role=User.Role.JOURNALIST).order_by('username'),
        'error': 'Only readers can subscribe to journalists.',
    })


# ---------------------------------------------------------------------------
# Third-party REST API (token-authenticated)
#
# Endpoints:
#   GET    /api/articles/            - all approved articles
#   POST   /api/articles/            - create an article (journalists only)
#   GET    /api/articles/subscribed/ - approved articles from publishers or
#                                       journalists the requesting reader follows
#   GET    /api/articles/<id>/       - retrieve a single article
#   PUT    /api/articles/<id>/       - update (editors: any; journalists: own only)
#   DELETE /api/articles/<id>/       - delete (same ownership rule as PUT)
#
# Object-level edit/delete checks reuse _can_edit_article/_can_delete_article
# above, so the API and the website can never drift out of sync on who's
# allowed to touch what.
# ---------------------------------------------------------------------------

class IsJournalist(permissions.BasePermission):
    """Grants access only to authenticated users with the JOURNALIST role."""
    message = 'Only journalists can create articles.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.JOURNALIST
        )


class ArticleListCreateAPIView(generics.ListCreateAPIView):
    """GET: every approved article, newest first.
    POST: create an article as the authenticated journalist."""
    serializer_class = ArticleSerializer

    def get_queryset(self):
        return Article.objects.filter(approved=True).order_by('-created_at')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), IsJournalist()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        # author is always the caller — never trust a client-supplied value.
        serializer.save(author=self.request.user)


class SubscribedArticleListAPIView(generics.ListAPIView):
    """GET: approved articles from publishers or journalists the requesting
    reader is subscribed to. Readers only — subscriptions aren't a concept
    for journalists/editors."""
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role != User.Role.READER:
            raise PermissionDenied('Only readers have subscriptions.')
        approved = Article.objects.filter(approved=True)
        return _visible_to_reader(approved, user).order_by('-created_at')


class ArticleDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """GET: retrieve an article — readers may only retrieve approved
    articles from a publisher or journalist they're subscribed to (same
    rule as the website's article_detail view); journalists and editors
    can retrieve any article. PUT/DELETE: gated by the same ownership rule
    as the website (editors: any article; journalists: only their own)."""
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Article.objects.all()
    # Explicitly exclude PATCH so the API surface matches the spec exactly
    # (PUT only for full updates); keep head/options for standard tooling.
    http_method_names = ['get', 'put', 'delete', 'head', 'options']

    def get_object(self):
        article = super().get_object()
        user = self.request.user
        method = self.request.method

        if user.role == User.Role.READER:
            visible = _visible_to_reader(
                Article.objects.filter(pk=article.pk, approved=True), user
            )
            if not visible.exists():
                # 404 rather than 403: don't confirm a restricted article's
                # existence to a caller who isn't allowed to see it.
                raise NotFound('Article not found.')

        if method == 'PUT' and not _can_edit_article(user, article):
            raise PermissionDenied('You do not have permission to update this article.')
        if method == 'DELETE' and not _can_delete_article(user, article):
            raise PermissionDenied('You do not have permission to delete this article.')

        return article
