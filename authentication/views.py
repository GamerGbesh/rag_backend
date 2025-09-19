from rag.serializers import UserRegistrationSerializer
from rag.models import Libraries
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken



# Create your views here.
def get_tokens_for_user(user):
    """This function generates refresh and access tokens for a user

    Args:
        user (django.db.User): The user object
    Returns:
        dict: The refresh and access tokens
    """
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@api_view(["POST"])
@csrf_exempt
def login_user(request):
    """This function authenticates a user and returns tokens"""
    username = request.data.get("username").lower()
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return Response(get_tokens_for_user(user))
    else:
        return Response({"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
    


@api_view(["POST"])
@csrf_exempt
def signup(request):
    """This function registers a new user"""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid(raise_exception=False):
        serializer.save()
        username = request.data.get("username").lower()
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        library_name = f"{username}'s Library"
        library_description = f"Library for {username}"
        Libraries.objects.create(library_name=library_name,
                                 library_description=library_description,
                                 creator=user,
                                 joinable=False)
        login(request, user)
        return Response(get_tokens_for_user(user))

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({"message": "Logged out"})