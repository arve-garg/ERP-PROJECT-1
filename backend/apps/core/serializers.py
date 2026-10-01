"""Core API serializers."""

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.models import (
    ActivityFeedItem,
    AuditLog,
    CompanySetting,
    Notification,
    Role,
    SavedFilter,
    User,
)


class RoleSerializer(serializers.ModelSerializer[Role]):
    class Meta:
        model = Role
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer[User]):
    roles = serializers.SlugRelatedField(
        many=True, slug_field="name", queryset=Role.objects.filter(is_deleted=False), required=False
    )
    password = serializers.CharField(write_only=True, required=False, min_length=12)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_deleted",
            "totp_required",
            "approval_status",
            "roles",
            "password",
            "date_joined",
            "employee_number",
            "department_name",
            "designation_title",
            "phone",
        ]
        read_only_fields = ["id", "is_staff", "is_deleted", "date_joined", "totp_required", "approval_status", "employee_number", "department_name", "designation_title", "phone"]

    employee_number = serializers.CharField(source="employee_profile.employee_number", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="employee_profile.department.name", read_only=True, allow_null=True)
    designation_title = serializers.CharField(source="employee_profile.designation.title", read_only=True, allow_null=True)
    phone = serializers.CharField(source="employee_profile.phone", read_only=True, allow_null=True)

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value, user=self.instance)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages)) from error
        return value

    def create(self, validated_data: dict[str, Any]) -> User:
        roles = validated_data.pop("roles", [])
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError(
                {"password": "A password is required when creating a user."}
            )
        actor = self.context["request"].user
        if getattr(actor, "is_authenticated", False):
            validated_data.setdefault("created_by", actor)
            validated_data.setdefault("updated_by", actor)
        user = User.objects.create_user(password=password, **validated_data)
        user.roles.set(roles)
        return user

    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        roles = validated_data.pop("roles", None)
        password = validated_data.pop("password", None)
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance


class UserProfileSerializer(serializers.ModelSerializer[User]):
    employee_number = serializers.CharField(source="employee_profile.employee_number", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="employee_profile.department.name", read_only=True, allow_null=True)
    designation_title = serializers.CharField(source="employee_profile.designation.title", read_only=True, allow_null=True)
    phone = serializers.CharField(source="employee_profile.phone", read_only=True, allow_null=True)

    roles: serializers.SlugRelatedField[Any] = serializers.SlugRelatedField(
        many=True, slug_field="name", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "roles",
            "totp_required",
            "approval_status",
            "employee_number",
            "department_name",
            "designation_title",
            "phone",
            "date_joined",
        ]
        read_only_fields = [
            "id", "email", "roles", "totp_required", "approval_status",
            "employee_number", "department_name", "designation_title", "phone", "date_joined"
        ]


class NotificationSerializer(serializers.ModelSerializer[Notification]):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "category",
            "title",
            "body",
            "target_url",
            "read_at",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["id", "read_at", "is_read", "created_at"]


class CompanySettingSerializer(serializers.ModelSerializer[CompanySetting]):
    class Meta:
        model = CompanySetting
        fields = ["id", "key", "value", "description", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class SavedFilterSerializer(serializers.ModelSerializer[SavedFilter]):
    class Meta:
        model = SavedFilter
        fields = ["id", "module", "name", "definition", "is_shared", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AuditLogSerializer(serializers.ModelSerializer[AuditLog]):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_email",
            "action",
            "model_label",
            "object_id",
            "changes",
            "occurred_at",
        ]
        read_only_fields = fields


class ActivityFeedSerializer(serializers.ModelSerializer[ActivityFeedItem]):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = ActivityFeedItem
        fields = ["id", "actor_email", "verb", "target_type", "target_id", "metadata", "created_at"]


class UserSearchResultSerializer(serializers.Serializer[dict[str, Any]]):
    entity = serializers.CharField()
    id = serializers.IntegerField()
    display_name = serializers.CharField()
