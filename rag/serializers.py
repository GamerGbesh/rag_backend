from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import serializers

from .models import Courses, Documents, Libraries, Admins, Members


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
    
    def validate(self, data):
        """Ensure user has less than 3 libraries."""
        user = self.context["request"].user
        count = Libraries.objects.filter(
            Q(members__user=user) | Q(creator=user, joinable=True)
        ).distinct().count()
        if count >= 3:
            raise serializers.ValidationError("You can only have 3 libraries.")
        return data
    

class JoinLibrariesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Libraries
        fields = ["library_name", "entry_key"]
        read_only_fields = ["id", "created", "creator", "joinable", "library_description"]

    def validate(self, attrs):
        count = Libraries.objects.filter(Q(members__user=self.context["request"].user) 
                                         | Q(creator=self.context["request"].user, joinable=True)).distinct().count()
        if count >= 2:
            raise serializers.ValidationError("You can only have 3 libraries.")

        library = get_object_or_404(Libraries, library_name=attrs["library_name"], entry_key=attrs["entry_key"])
        member_count = Members.objects.filter(library=library).count()
        
        if member_count >= 15:
            raise serializers.ValidationError("Library is full.")
        elif not library.joinable:
            raise serializers.ValidationError("This library is not joinable.")
        elif library.creator == self.context["request"].user:
            raise serializers.ValidationError("You are the creator of this library.")
        elif library.members.filter(user=self.context["request"].user).exists():
            raise serializers.ValidationError("You are already a member of this library.")
        
        self.library = library

        return attrs



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
    

class RemoveMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    library_id = serializers.IntegerField()

    def validate(self, attrs):
        user = get_object_or_404(User, id=attrs["user_id"])
        library = get_object_or_404(Libraries, id=attrs["library_id"])
        member = Members.objects.filter(user=user, library=library)
        
        if not member.exists():
            raise serializers.ValidationError("This user is not a member of the specified library.")
        
        attrs["user"] = user
        attrs["library"] = library
        attrs["member"] = member.first()
        return attrs
    

class QueryLLMSerializer(serializers.Serializer):
    query = serializers.CharField(required=True)
    course_id = serializers.IntegerField(required=True)