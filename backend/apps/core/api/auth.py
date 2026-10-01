"""Authentication, account recovery, and optional TOTP endpoints."""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django_otp.plugins.otp_totp.models import TOTPDevice
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Notification, User
from apps.hr.models import Department, Designation, EmployeeProfile


class LoginThrottle(AnonRateThrottle):
    scope = "auth"


class PasswordResetThrottle(AnonRateThrottle):
    scope = "password_reset"


class TwoFactorThrottle(UserRateThrottle):
    scope = "two_factor"


class LoginSerializer(TokenObtainPairSerializer):
    """Email/password login, with OTP validation for accounts that require 2FA."""

    otp_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        otp_code = attrs.pop("otp_code", "")
        data: dict[str, Any] = super().validate(attrs)
        user = self.user
        if user is None:
            raise serializers.ValidationError("The supplied credentials are invalid.")
        profile = EmployeeProfile.objects.filter(user=user).select_related("department", "designation").first()
        if user.totp_required:
            devices = TOTPDevice.objects.filter(user=user, confirmed=True)
            if not otp_code or not any(device.verify_token(otp_code) for device in devices):
                raise serializers.ValidationError(
                    {"otp_code": "A valid authenticator code is required."}
                )
        data["user"] = {
            "id": user.pk,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "totp_required": user.totp_required,
            "approval_status": user.approval_status,
            "employee_number": profile.employee_number if profile else None,
            "department_name": profile.department.name if profile else None,
            "designation_title": profile.designation.title if profile else None,
            "phone": profile.phone if profile else None,
            "roles": list(user.roles.values_list("name", flat=True))
            + (
                ["Admin"]
                if user.is_superuser and not user.roles.filter(name="Admin").exists()
                else []
            ),
        }
        return data


class LoginResponseSerializer(serializers.Serializer[dict[str, Any]]):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.JSONField()


class MessageSerializer(serializers.Serializer[dict[str, Any]]):
    detail = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()


class TOTPSetupResponseSerializer(serializers.Serializer[dict[str, Any]]):
    secret = serializers.CharField()
    provisioning_uri = serializers.CharField()


class LoginView(GenericAPIView[Any]):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginThrottle]
    serializer_class = LoginSerializer

    @extend_schema(responses={200: LoginResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class LogoutSerializer(serializers.Serializer[dict[str, str]]):
    refresh = serializers.CharField()

    def validate_refresh(self, value: str) -> str:
        try:
            RefreshToken(cast(Any, value))
        except TokenError as error:
            raise serializers.ValidationError("Refresh token is invalid or expired.") from error
        return value


class LogoutView(GenericAPIView[Any]):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(responses={204: None})
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = RefreshToken(serializer.validated_data["refresh"])
        if str(token.get("user_id")) != str(request.user.pk):
            return Response(
                {"detail": "The refresh token does not belong to this account."}, status=400
            )
        token.blacklist()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetView(GenericAPIView[Any]):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetThrottle]
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(responses={200: MessageSerializer})
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        form = PasswordResetForm({"email": email})
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            extra_email_context={
                "reset_base_url": settings.DEVERP_FRONTEND_URL.rstrip("/") + "/reset-password",
            },
        )
        return Response(
            {"detail": "If the account exists, password reset instructions have been sent."}
        )


class PasswordResetConfirmSerializer(serializers.Serializer[dict[str, Any]]):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=12)


class PasswordResetConfirmView(GenericAPIView[Any]):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetThrottle]
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(responses={200: MessageSerializer})
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            user = User.objects.get(pk=user_id, is_active=True, is_deleted=False)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"detail": "The reset link is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not default_token_generator.check_token(user, serializer.validated_data["token"]):
            return Response(
                {"detail": "The reset link is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(serializer.validated_data["new_password"], user=user)
        except ValidationError as error:
            return Response(
                {"new_password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        for outstanding in OutstandingToken.objects.filter(user=user).iterator():
            BlacklistedToken.objects.get_or_create(token=outstanding)
        return Response({"detail": "Password has been reset."})


class EmptySerializer(serializers.Serializer[dict[str, Any]]):
    pass


class TOTPSetupView(GenericAPIView[Any]):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TwoFactorThrottle]
    serializer_class = EmptySerializer

    @extend_schema(request=None, responses={200: TOTPSetupResponseSerializer})
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        if user.totp_required:
            return Response({"detail": "Two-factor authentication is already enabled."}, status=400)
        TOTPDevice.objects.filter(user=user, confirmed=False).delete()
        device = TOTPDevice.objects.create(user=user, name="Authenticator", confirmed=False)
        return Response({"secret": device.key, "provisioning_uri": device.config_url})


class TOTPCodeSerializer(serializers.Serializer[dict[str, str]]):
    code = serializers.RegexField(r"^\d{6}$")


class TOTPConfirmView(GenericAPIView[Any]):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TwoFactorThrottle]
    serializer_class = TOTPCodeSerializer

    @extend_schema(responses={200: MessageSerializer})
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = (
            TOTPDevice.objects.filter(user=cast(User, request.user), confirmed=False)
            .order_by("-id")
            .first()
        )
        if device is None or not device.verify_token(serializer.validated_data["code"]):
            return Response({"code": ["The authenticator code is invalid."]}, status=400)
        device.confirmed = True
        device.save(update_fields=["confirmed"])
        user = cast(User, request.user)
        user.totp_required = True
        user.save(update_fields=["totp_required"])
        return Response({"detail": "Two-factor authentication enabled."})


class TOTPDisableView(GenericAPIView[Any]):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TwoFactorThrottle]
    serializer_class = TOTPCodeSerializer

    @extend_schema(responses={200: MessageSerializer})
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = cast(User, request.user)
        devices = TOTPDevice.objects.filter(user=user, confirmed=True)
        if not any(device.verify_token(serializer.validated_data["code"]) for device in devices):
            return Response({"code": ["The authenticator code is invalid."]}, status=400)
        devices.delete()
        user.totp_required = False
        user.save(update_fields=["totp_required"])
        return Response({"detail": "Two-factor authentication disabled."})


class RegisterThrottle(AnonRateThrottle):
    scope = "register"


class RegisterSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    employee_number = serializers.CharField(max_length=30)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_deleted=False)
    )
    designation = serializers.PrimaryKeyRelatedField(
        queryset=Designation.objects.filter(is_deleted=False, department__is_deleted=False)
    )
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=12)
    password_confirm = serializers.CharField(write_only=True, min_length=12)

    def validate_employee_number(self, value: str) -> str:
        value = value.strip()
        if EmployeeProfile.objects.filter(employee_number__iexact=value).exists():
            raise serializers.ValidationError("An employee code with this value already exists.")
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        if attrs["designation"].department_id != attrs["department"].id:
            raise serializers.ValidationError(
                {"designation": "The selected designation must belong to the selected department."}
            )
        try:
            validate_password(attrs["password"])
        except ValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)}) from error
        return attrs


class RegisterView(GenericAPIView[Any]):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RegisterThrottle]
    serializer_class = RegisterSerializer

    @extend_schema(responses={201: MessageSerializer})
    @transaction.atomic
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.create_user(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"].strip(),
            last_name=data.get("last_name", "").strip(),
            is_active=True,
            approval_status=User.ApprovalStatus.PENDING,
        )
        EmployeeProfile.objects.create(
            user=user,
            employee_number=data["employee_number"].strip(),
            department=data["department"],
            designation=data["designation"],
            phone=data.get("phone", "").strip(),
            created_by=user,
            updated_by=user,
        )
        admins = User.objects.filter(is_superuser=True, is_active=True, is_deleted=False).union(
            User.objects.filter(roles__name="Admin", is_active=True, is_deleted=False)
        )
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                category="user_registration",
                title="New user registration",
                body=f"{user.get_full_name() or user.email} requested access for {data['department'].name}.",
                target_url="/access",
            )
        return Response(
            {"detail": "Application submitted successfully. You can sign in to check your approval status."},
            status=status.HTTP_201_CREATED,
        )


class RegistrationOptionsView(GenericAPIView[Any]):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request: Request) -> Response:
        departments = list(
            Department.objects.filter(is_deleted=False).values("id", "name", "code").order_by("name")
        )
        designations = list(
            Designation.objects.filter(is_deleted=False, department__is_deleted=False)
            .values("id", "title", "department_id")
            .order_by("title")
        )
        return Response({"departments": departments, "designations": designations})
