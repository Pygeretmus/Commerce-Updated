from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    email = models.EmailField(unique=True)

    class Meta(AbstractUser.Meta):
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(Lower('email'), name='uniq_user_email_ci')
        ]
