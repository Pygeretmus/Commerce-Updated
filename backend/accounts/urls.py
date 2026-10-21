from django.urls import path

from .views import AccountCreateView, CurrentAccountView

app_name = 'accounts'

urlpatterns = [
    path('accounts/', AccountCreateView.as_view(), name='account-create'),
    path('accounts/me/', CurrentAccountView.as_view(), name='account-me'),
]
