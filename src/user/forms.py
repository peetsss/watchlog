from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "password1", "password2")

    def __init__(self, *args, **kwargs) -> None:
        super(SignUpForm, self).__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control bg-dark text-light pt-1",
            }
        )
        self.fields["username"].help_text = ""
        self.fields["password1"].widget.attrs.update(
            {
                "class": "form-control bg-dark text-light",
            }
        )
        self.fields["password1"].help_text = ""
        self.fields["password2"].widget.attrs.update(
            {
                "class": "form-control bg-dark text-light",
            }
        )
        self.fields["password2"].help_text = ""


class AuthForm(AuthenticationForm):
    def __init__(self, *args, **kwargs) -> None:
        super(AuthForm, self).__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control bg-dark text-light",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "form-control bg-dark text-light",
            }
        )
