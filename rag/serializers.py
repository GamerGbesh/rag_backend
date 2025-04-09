from rest_framework import serializers
from .models import  Courses, Documents, Libraries, Admins, Members
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)


    class Meta:
        model = User
        fields = [ "username", "email", "password", "password2"]

    
    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Passwords must match"})
        return data
    
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )
        return user

class CoursesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Courses
        fields = "__all__"
        read_only_fields = ["id", "created_at", "library"]

class DocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documents
        fields = "__all__"
        read_only_fields = ["id", "uploaded_at", "user"]

class LibrariesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Libraries
        fields = "__all__"
        read_only_fields = ["id", "created", "creator", "joinable"]
    
    def validate_library_name(self, value):
        """Ensure the user does not create duplicate libraries with the same name."""
        user = self.context["request"].user
        if Libraries.objects.filter(library_name=value, creator=user).exists():
            raise serializers.ValidationError("A library with this name already exists for this user.")
        return value

class JoinLibrariesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Libraries
        fields = ["library_name", "entry_key"]
        read_only_fields = ["id", "created", "creator", "joinable", "library_description"]



class MembersSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Members
        fields = "__all__"
        read_only_fields = ["id", "user", "library"]


    def to_representation(self, instance):
        data = super().to_representation(instance)
        is_admin = Admins.objects.filter(user=instance.user, library=instance.library).exists()
        data["is_admin"] = is_admin
        return data
    