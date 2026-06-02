from rest_framework.permissions import BasePermission


def _is_developer(user) -> bool:
    groups = getattr(user, 'claims', {}).get('groups', [])
    return '/developers' in groups or 'developers' in groups


class IsDeveloper(BasePermission):
    """Autorise uniquement les membres du groupe LDAP 'developers'."""
    message = "Réservé aux membres du groupe 'developers'."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and _is_developer(request.user))


class HasSensorAccess(BasePermission):
    """Autorise si l'utilisateur est developer OU possède un accès explicite au capteur."""
    message = "Vous n'avez pas accès à ce capteur."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if _is_developer(request.user):
            return True
        email = getattr(request.user, 'email', '')
        return obj.user_accesses.filter(user_email=email).exists()
