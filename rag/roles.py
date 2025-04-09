from .models import Admins, Libraries

def is_creator(user, library: Libraries) -> bool:
    """
    Check if the user is a creator of the specified library.
    """
    return library.creator == user


def is_admin(user, library: Libraries) -> bool:
    """
    Check if the user is an admin of the specified library.
    """
    return Admins.objects.filter(user=user, library=library).exists()


def has_edit_permission(user, library: Libraries) -> bool:
    """
    Check if the user has edit permissions for the specified library.
    """
    return is_creator(user, library) or is_admin(user, library)