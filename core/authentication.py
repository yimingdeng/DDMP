from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class PhoneEmailUsernameBackend(ModelBackend):
    """Allow username, email, or phone number as the login identifier."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        login_identifier = (username or kwargs.get(UserModel.USERNAME_FIELD) or "").strip()
        if not login_identifier or password is None:
            return None

        users = UserModel._default_manager.filter(
            Q(username__iexact=login_identifier)
            | Q(email__iexact=login_identifier)
            | Q(profile__phone=login_identifier)
        )
        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
