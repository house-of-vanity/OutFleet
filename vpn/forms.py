from django import forms
from .models import User
from .server_plugins import Server

class UserForm(forms.ModelForm):
    servers = forms.ModelMultipleChoiceField(
        queryset=Server.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'comment', 'servers']
