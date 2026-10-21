from django.urls import path

from .views import AccountCreateView, AccountDestroyView, AccountPasswordChangeView, CurrentAccountView

app_name = 'accounts'

urlpatterns = [
    path('accounts/', AccountCreateView.as_view(), name='account-create'),
    path('accounts/me/', CurrentAccountView.as_view(), name='account-me'),
    path('accounts/password/', AccountPasswordChangeView.as_view(), name='account-password'),
    path('accounts/destroy/', AccountDestroyView.as_view(), name='account-destroy'),
]
