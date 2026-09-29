"""Account adapter enforcing administrator-provisioned user accounts."""

from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpRequest


class InvitationOnlyAccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return False
