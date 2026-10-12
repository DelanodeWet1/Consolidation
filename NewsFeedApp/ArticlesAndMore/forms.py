from django import forms

from .models import Article, Newsletter, Publisher, User


class ArticleForm(forms.ModelForm):
    """Form for creating or editing an Article."""

    class Meta:
        model = Article
        fields = ['title', 'content', 'publisher']

    def __init__(self, *args, **kwargs):
        """Make the publisher field optional, since publishing
        independently (with no publisher) is always allowed."""
        super().__init__(*args, **kwargs)
        # Publishing independently (no publisher) is always allowed.
        self.fields['publisher'].required = False
        self.fields['publisher'].empty_label = 'Independent (no publisher)'


class NewsletterForm(forms.ModelForm):
    """Form for creating or editing a Newsletter."""

    class Meta:
        model = Newsletter
        fields = ['title', 'description', 'articles', 'publisher']
        widgets = {
            'articles': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        """Make the publisher field optional, matching ArticleForm.
        Also, restrict the articles field to only show articles that are approved and belong to the same publisher as the newsletter (if any)."""
        super().__init__(*args, **kwargs)
        self.fields['publisher'].required = False
        self.fields['publisher'].empty_label = 'Independent (no publisher)'
        self.fields['articles'].queryset = Article.objects.filter(approved=True)


class PublisherForm(forms.ModelForm):
    """Form used by an editor to create a new Publisher.

    Only exposes the Publisher's own fields. The editor who submits this
    form is auto-assigned to the resulting Publisher by
    views.publisher_create - that assignment isn't part of the form
    itself.
    """

    class Meta:
        model = Publisher
        fields = ['name']


class AssignJournalistForm(forms.Form):
    """Form used by an editor to assign a journalist to the publisher
    they're themselves assigned to.

    Only journalists with no publisher_j set are offered, since a
    journalist can only work for one publisher at a time - the view is
    responsible for checking the submitting editor actually belongs to
    the target publisher.
    """

    journalist = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='Journalist',
        help_text='Only journalists not already assigned to a publisher are listed.',
    )

    def __init__(self, *args, **kwargs):
        """Restrict the journalist choices to unassigned journalists."""
        super().__init__(*args, **kwargs)
        self.fields['journalist'].queryset = User.objects.filter(
            role=User.Role.JOURNALIST, publisher_j__isnull=True
        ).order_by('username')
