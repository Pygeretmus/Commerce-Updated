from ..models import Notification


def note(user, listing, **kwargs) -> Notification:
    return Notification.objects.create(recipient=user, kind=kwargs.pop('kind', 'lost'), listing=listing, **kwargs)
