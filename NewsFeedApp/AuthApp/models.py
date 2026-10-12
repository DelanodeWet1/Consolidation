"""Models for the AuthApp app: password-reset tokens."""
from django.db import models
from django.conf import settings

class ResetToken(models.Model):
    """A single-use, expiring token issued when a user requests a
    password reset. Created by views.generate_reset_url and consumed by
    views.reset_user_password / views.reset_password."""

    # Reference to the user who requested the password reset
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Token string, unique to avoid duplicates
    token = models.CharField(max_length=255, unique=True)
    # When this token expires
    expiry_date = models.DateTimeField()
    # Whether this token has already been used
    used = models.BooleanField(default=False)

    def __str__(self):
        """Return a short, safe-to-log summary (token truncated)."""
        # Show a short summary for easier debugging
        return f"ResetToken(user={self.user.username}, token={self.token[:10]}..., used={self.used})"
