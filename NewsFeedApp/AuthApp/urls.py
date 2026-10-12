"""URL routing for AuthApp: login, registration, logout, and the
password-reset flow (request -> emailed link -> set new password)."""
from django.urls import path
from . import views

app_name = 'AuthApp'

urlpatterns = [
    # Default page: login form
    path('', views.login_user, name='login'),

    # Registration page where users can sign up
    path('register/', views.register_user, name='register'),

    # Logs the user out
    path('logout/', views.logout_user, name='logout'),

    # Welcome page after successful login
    path('welcome/', views.welcome, name='welcome'),

    # Alternate login URL (fallback)
    path('alter_login/', views.login_user, name='alterlogin'),

    # Page where users request a password reset by entering their email
    path('request-password-reset/', views.send_password_reset, name='request_password_reset'),

    # Page users visit from the email link to enter a new password
    # The token in the URL is used to verify the password reset request
    path('reset_password/<str:token>/', views.reset_user_password, name='password_reset_form'),

    # Handles the form submission to actually change the password (POST request)
    path('reset_password/', views.reset_password, name='reset_password'),
]
