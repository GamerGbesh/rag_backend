import pytest
from rag.serializers import (
    UserRegistrationSerializer,
    LibrariesSerializer,
    CoursesSerializer,
    DocumentsSerializer,
    MembersSerializer
)
from rag.models import Libraries, Members, Admins
from django.contrib.auth import get_user_model
from django.test import RequestFactory

User = get_user_model()

@pytest.mark.django_db
def test_user_registration_serializer_success():
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "strongpassword",
        "password2": "strongpassword"
    }
    serializer = UserRegistrationSerializer(data=data)
    assert serializer.is_valid()
    user = serializer.save()
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.check_password("strongpassword")


@pytest.mark.django_db
def test_user_registration_serializer_password_mismatch():
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "password1",
        "password2": "password2"
    }
    serializer = UserRegistrationSerializer(data=data)
    assert not serializer.is_valid()
    assert "password" in serializer.errors


@pytest.mark.django_db
def test_libraries_serializer_duplicate_name():
    factory = RequestFactory()
    user = User.objects.create_user(username="user1", password="password")
    request = factory.get("/")
    request.user = user

    # Create a library
    Libraries.objects.create(
        library_name="Test Library",
        creator=user,
        joinable=True,
    )

    # Try creating another with the same name
    serializer = LibrariesSerializer(
        data={"library_name": "Test Library", "library_description": "Another one"},
        context={"request": request}
    )
    assert not serializer.is_valid()
    assert "library_name" in serializer.errors


@pytest.mark.django_db
def test_courses_serializer_creation():
    library = Libraries.objects.create(library_name="My Lib", creator=None, joinable=True)
    course_data = {
        "course_name": "Physics 101",
        "course_description": "Intro Physics",
        "library": library.id
    }
    serializer = CoursesSerializer(data=course_data)
    # library field is read_only, so need to use serializer.save()
    assert serializer.is_valid()


@pytest.mark.django_db
def test_documents_serializer_creation():
    library = Libraries.objects.create(library_name="Lib1", creator=None, joinable=True)
    course = library.courses_set.create(course_name="Math", course_description="Math course")

    data = {
        "file": None,  # You might need to use a fake file
        "course": course.id
    }
    serializer = DocumentsSerializer(data=data)
    assert serializer.is_valid()  # assuming file is optional or mocked

@pytest.mark.django_db
def test_members_serializer_admin_flag():
    user = User.objects.create_user(username="memberuser", password="password")
    library = Libraries.objects.create(library_name="LibAdmin", creator=None, joinable=True)
    member = Members.objects.create(user=user, library=library)
    Admins.objects.create(user=user, library=library)

    serializer = MembersSerializer(instance=member)
    data = serializer.data

    assert data["is_admin"] is True
