"""Views for AuthApp: login, registration, logout, and the password-reset
flow (request reset -> emailed link -> set new password).
"""
from django.shortcuts import render, redirect  # To show HTML pages and redirect users
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
)  # Functions to handle login and logout
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
)  # For redirecting users or sending responses
from django.urls import reverse, reverse_lazy  # Helps get URLs by their names
from django.contrib.auth.decorators import (
    login_required,
)  # Makes sure only logged-in users can access pages
from datetime import datetime
import secrets  # For generating secure random tokens
from datetime import timedelta
from hashlib import sha1  # To hash tokens securely
from django.utils import timezone  # Better way to handle dates and times in Django
from django.core.exceptions import (
    ObjectDoesNotExist,
)  # For handling cases when an object is not found
from .utils import (
    generate_reset_url,
    build_email,
)  # Helper functions for email and token generation
from .models import ResetToken  # Our custom model to store reset tokens
from django.conf import settings

from django.core.mail import EmailMessage  # To send emails
from django.contrib.auth.hashers import make_password  # To hash passwords before saving

User = (
    get_user_model()
)  # Resolves to the project's custom User model (ArticlesAndMore.User)


# This function handles user login
def login_user(request):
    """Show the login form on GET; on POST, authenticate the submitted
    username/password, log the user in, extend their session to expire
    on 30 Dec 2026, and redirect to the welcome page. Re-shows the form
    with an error on invalid credentials."""
    # When the login form is submitted
    if request.method == "POST":
        # Get username and password from the form
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Check if the username and password match a user in the database
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)  # Log the user in and start their session

            # Set the session to expire on 30 Dec 2026 (so user stays logged in until then)
            exp_date = datetime(2026, 12, 30)
            now = datetime.now()
            expiry_seconds = int((exp_date - now).total_seconds())
            if expiry_seconds > 0:
                request.session.set_expiry(
                    expiry_seconds
                )  # Set the expiry time for the session

            # Save some user info in the session (optional, but useful)
            request.session["user_id"] = user.id
            request.session["username"] = user.username

            # Redirect user to the welcome page after successful login
            return HttpResponseRedirect(reverse("AuthApp:welcome"))
        else:
            # If login failed, reload login page with an error message
            return render(
                request, "AuthApp/login.html", {"error": "Invalid credentials"}
            )

    # If the user just opened the login page, show the login form
    return render(request, "AuthApp/login.html")


# This function handles user registration (signing up)
def register_user(request):
    """Show the registration form on GET; on POST, validate the submitted
    data (matching passwords, unique email, valid role), create the User
    with that role, log them in, and redirect to the welcome page."""
    if request.method == "POST":
        # Get data from the form
        username = request.POST.get("username")
        password = request.POST.get("password")
        confpassword = request.POST.get("password_confirmation")
        email = request.POST.get("email")
        # Form values are lowercase ('reader'/'journalist'/'editor'); the
        # User.Role choices are uppercase, so normalise before using it.
        role = request.POST.get("role", "").upper()

        if password != confpassword:
            return render(
                request,
                "AuthApp/register.html",
                {"error": "Passwords do not match. Please try again."},
            )

        # Check for the same email on an exisitng account
        email_list = list(User.objects.values_list("email", flat=True))
        if email in email_list:
            return render(
                request,
                "AuthApp/register.html",
                {
                    "error": "Email already associated with an account. Please use another email."
                },
            )

        # Check for the same username on an exisitng account
        name_list = list(User.objects.values_list("username", flat=True))
        if username in name_list:
            return render(
                request,
                "AuthApp/register.html",
                {
                    "error": "Username already associated with an account. Please use another username."
                },
            )

        if role not in User.Role.values:
            return render(
                request,
                "AuthApp/register.html",
                {"error": "Please select a valid role."},
            )

        # Create the user against the project's custom User model and set role.
        user = User.objects.create_user(
            username=username, password=password, email=email
        )
        user.role = role
        user.save()

        login(request, user)  # Log the new user in automatically

        # Redirect to welcome page after registration
        return redirect(reverse("AuthApp:welcome"))

    # If user visits registration page, show the registration form
    return render(request, "AuthApp/register.html")


# Helper function to change a user's password securely
def change_user_password(username, new_password):
    """Set and save a new (hashed) password for the user with the given
    username. Not called anywhere in this app yet - kept as a small
    reusable helper for the reset flow."""
    user = User.objects.get(username=username)  # Find user by username

    user.set_password(new_password)  # Set the new password (hashed automatically)

    user.save()  # Save changes to the database


# Logs the user out and redirects to login page
def logout_user(request):
    """Log out the current user and redirect to the login page."""
    if request.user is not None:
        logout(request)  # Log out the current user
        return HttpResponseRedirect(reverse("AuthApp:login"))


# Only logged-in users can see the welcome page
@login_required(login_url=reverse_lazy("AuthApp:login"))
def welcome(request):
    """Show the welcome/landing page for a logged-in user."""
    return render(request, "AuthApp/welcome.html")  # Show the welcome page


# Creates the email object to send for password reset
def build_email(user, reset_url):
    """Build (but don't send) the password-reset email for a user,
    containing the given reset URL."""
    subject = "Password Reset"
    user_email = user.email
    domain_email = settings.EMAIL_HOST_USER  # The "from" email address for the email
    body = f"Hi {user.username},\nHere is your link to reset your password: {reset_url}"

    email = EmailMessage(subject, body, domain_email, [user_email])
    return email


# Creates a secure reset URL with a token that expires in 5 minutes
def generate_reset_url(user):
    """Create a ResetToken for the user (hashed, expiring in 5 minutes)
    and return the full password-reset URL containing the raw token."""
    domain = "http://127.0.0.1:8000"

    token = secrets.token_urlsafe(16)  # Generate a random secure token

    expiry_date = timezone.now() + timedelta(minutes=5)  # Token expires in 5 minutes

    hashed_token = sha1(token.encode()).hexdigest()  # Hash the token to store securely

    # Save the hashed token and expiry date to the database
    reset_token = ResetToken.objects.create(
        user=user, token=hashed_token, expiry_date=expiry_date
    )

    path = reverse("AuthApp:password_reset_form", kwargs={"token": token})
    url = f"{domain}{path}"
    return url


# Handles sending the password reset email after user submits their email
def send_password_reset(request):
    """Show the 'request a reset' form on GET; on POST, generate and
    email a reset link if the address matches a user. Always shows the
    same confirmation page regardless of whether the email matched, so
    the response can't be used to enumerate registered emails."""
    if request.method == "POST":
        user_email = request.POST.get("email")
        try:
            user = User.objects.get(email=user_email)  # Find user by email
            reset_url = generate_reset_url(user)  # Generate reset link with token
            email = build_email(user, reset_url)  # Create the email message
            email.send()  # Send the email

            # Show a confirmation page that email was sent
            return render(
                request, "AuthApp/reset_email_sent.html", {"email": user_email}
            )

        except ObjectDoesNotExist:
            # Even if no user found, still show confirmation (to avoid info leaks)
            return render(
                request, "AuthApp/reset_email_sent.html", {"email": user_email}
            )

    # Show the form where user can enter their email
    return render(request, "AuthApp/request_password_reset.html")


# This view is called when user clicks the reset link in their email
def reset_user_password(request, token):
    """Validate the reset token from the URL: show the expired-token page
    if it's expired, the invalid-token page if it doesn't exist, or
    otherwise stash the user/token in the session and show the
    new-password form."""
    hashed_token = sha1(token.encode()).hexdigest()  # Hash the token from URL

    try:
        user_token = ResetToken.objects.get(token=hashed_token)  # Look for token in DB

        # Check if the token expired
        # if user_token.expiry_date.replace(tzinfo=None) < datetime.now():
        if user_token.expiry_date < timezone.now():
            user_token.delete()  # Delete expired token
            return render(
                request, "AuthApp/password_reset_expired.html"
            )  # Show expired token message

        # Save user ID and token in session to verify next step
        request.session["user_id"] = user_token.user.id
        request.session["reset_token"] = token

        # Show the password reset form
        return render(request, "AuthApp/password_reset.html", {"token": token})

    except ResetToken.DoesNotExist:
        # Token not found or already used
        return render(request, "AuthApp/password_reset_invalid.html")


# Handles the password reset form submission (when user enters new password)
def reset_password(request):
    """Handle the new-password form submission: validate the session
    data and matching passwords, re-check the token hasn't expired, then
    update the user's password, delete the used token, clear the
    session, and redirect to login. Redirects to login on GET."""
    if request.method == "POST":
        user_id = request.session.get("user_id")
        token = request.session.get("reset_token")
        password = request.POST.get("password")
        password_conf = request.POST.get("password_conf")

        # Check if all required data is present
        if not all([user_id, token, password, password_conf]):
            return render(
                request,
                "AuthApp/password_reset.html",
                {"error": "Missing fields or session expired.", "token": token},
            )

        # Check if passwords match
        if password != password_conf:
            return render(
                request,
                "password_reset.html",
                {"error": "Passwords do not match.", "token": token},
            )

        try:
            user = User.objects.get(pk=user_id)  # Find user by user_id
            hashed_token = sha1(token.encode()).hexdigest()
            reset_token = ResetToken.objects.get(token=hashed_token)

            # Check token expiry again (just to be sure)
            if reset_token.expiry_date < timezone.now():
                reset_token.delete()
                return render(request, "AuthApp/password_reset_expired.html")

            # Update the user's password (hashed securely)
            user.password = make_password(password)
            user.save()

            # Delete the token and clear session info
            reset_token.delete()
            request.session.flush()

            # Redirect user to login page after successful password reset
            return HttpResponseRedirect(reverse("AuthApp:login"))

        except (User.DoesNotExist, ResetToken.DoesNotExist):
            return render(request, "password_reset_invalid.html")

    # If the page was accessed with GET or any other method, redirect to login page
    return HttpResponseRedirect(reverse("AuthApp:login"))
