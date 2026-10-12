from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import views

app_name = 'ArticlesAndMore'  # This helps Django know these URLs belong to the ArticlesAndMore app

urlpatterns = [
    # Home page: shows the list of articles visible to the current user
    path('', views.article_list, name='article_list'),

    # URL pattern for displaying details of a specific article
    path('article/<int:pk>/', views.article_detail, name='article_detail'),

    # URL pattern for creating a new article
    path('article/new/', views.article_create, name='article_create'),

    # URL pattern for updating an existing article
    path('article/<int:pk>/edit/', views.article_update, name='article_update'),

    # URL pattern for deleting an existing article
    path('article/<int:pk>/delete/', views.article_delete, name='article_delete'),

    # URL pattern for an editor to approve/unapprove an article
    path('article/<int:pk>/approve/', views.article_approve, name='article_approve'),

    # Internal API endpoint that receives newly-approved articles
    path('api/approved/', views.api_approved, name='api_approved'),

    # --- Third-party REST API (token-authenticated) ---

    # Exchange a username/password for an auth token (DRF built-in view).
    # POST {"username": "...", "password": "..."} -> {"token": "..."}
    path('api/token/', obtain_auth_token, name='api_token'),

    # GET: all approved articles. POST: create an article (journalists only).
    path('api/articles/', views.ArticleListCreateAPIView.as_view(), name='api_article_list_create'),

    # GET: approved articles from publishers/journalists the reader follows.
    path('api/articles/subscribed/', views.SubscribedArticleListAPIView.as_view(), name='api_article_subscribed'),

    # GET: retrieve. PUT: update (editors: any; journalists: own only).
    # DELETE: same ownership rule as PUT.
    path('api/articles/<int:pk>/', views.ArticleDetailAPIView.as_view(), name='api_article_detail'),

    # Page showing the list of newsletters visible to the current user
    path('newsletters/', views.newsletter_list, name='newsletter_list'),

    # URL pattern for displaying details of a specific newsletter
    path('newsletter/<int:pk>/', views.newsletter_detail, name='newsletter_detail'),

    # URL pattern for creating a new newsletter
    path('newsletter/new/', views.newsletter_create, name='newsletter_create'),

    # URL pattern for updating an existing newsletter
    path('newsletter/<int:pk>/edit/', views.newsletter_update, name='newsletter_update'),

    # URL pattern for deleting an existing newsletter
    path('newsletter/<int:pk>/delete/', views.newsletter_delete, name='newsletter_delete'),

    # Page showing the list of all publishers
    path('publishers/', views.publisher_list, name='publisher_list'),

    # URL pattern for an editor to create a new publisher (auto-assigns them to it)
    path('publisher/new/', views.publisher_create, name='publisher_create'),

    # URL pattern for viewing a single publisher
    path('publisher/<int:pk>/', views.publisher_detail, name='publisher_detail'),

    # URL pattern for a reader to subscribe/unsubscribe to a publisher
    path('publisher/<int:pk>/subscribe/', views.toggle_publisher_subscription,
         name='toggle_publisher_subscription'),

    # URL pattern for an unassigned editor to assign themselves to a publisher
    path('publisher/<int:pk>/assign/', views.publisher_assign_self, name='publisher_assign_self'),

    # URL pattern for an editor to leave the publisher they're assigned to
    path('publisher/<int:pk>/leave/', views.publisher_leave, name='publisher_leave'),

    # URL pattern for an editor to assign an unassigned journalist to their publisher
    path('publisher/<int:pk>/assign-journalist/', views.publisher_assign_journalist,
         name='publisher_assign_journalist'),

    # URL pattern for an editor to remove a journalist from their publisher
    path('publisher/<int:pk>/remove-journalist/<int:journalist_id>/', views.publisher_remove_journalist,
         name='publisher_remove_journalist'),

    # Page showing the list of all journalists
    path('journalists/', views.journalist_list, name='journalist_list'),

    # URL pattern for a reader to subscribe/unsubscribe to a journalist
    path('journalist/<int:pk>/subscribe/', views.toggle_journalist_subscription,
         name='toggle_journalist_subscription'),
]
