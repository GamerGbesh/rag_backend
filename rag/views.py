from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.db.models import Q

from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

import logging

from .exceptions import LLMServiceError
from .models import Libraries, Courses, Documents, Members, Admins
from .permissions import IsLibraryCreator, IsLibraryCreatorOrAdmin, IsLibraryMember 
from .serializers import LibrariesSerializer, CoursesSerializer, DocumentsSerializer, MembersSerializer, JoinLibrariesSerializer, QueryLLMSerializer, RemoveMemberSerializer
from .roles import has_edit_permission, is_creator
from .services.langgraph_service import LangGraphService
from .services.document_service import DocumentService
from .services.course_service import CourseService

logger = logging.getLogger(__name__)



# Create your views here.
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_library(request):
    """Create a new library"""
    logger.info("create_library called by user=%s data=%s", request.user.username if request.user else None, request.data)
    serializer = LibrariesSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save(creator=request.user)
    logger.info("Library created by user=%s", request.user.username if request.user else None)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def join_library(request):
    """Join an existing library with an entry key."""
    logger.info("join_library called by user=%s data=%s", request.user.username if request.user else None, request.data)
    serializer = JoinLibrariesSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        library = serializer.library
        Members.objects.get_or_create(user=request.user, library=library)
        logger.info("User %s joined library", request.user.username if request.user else None)
        return Response({"message": "Library joined successfully"})
    

@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsLibraryCreator])
def remove_member(request):
    """Remove a member from a library."""
    serializer = RemoveMemberSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    library = serializer.validated_data["library"]
    member = serializer.validated_data["member"]

    try:
        admin = Admins.objects.get(user=user, library=library)
        admin.delete()
    except Admins.DoesNotExist:
        pass

    member.delete()
    return Response({"message": "Member removed successfully"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def leave_library(request):
    """Member leaves a library."""
    library_id = request.data.get("library_id")
    library = Libraries.objects.get(id=library_id)
    user = request.user
    member = get_object_or_404(Members, user=user, library=library)
    try:
        admin = Admins.objects.get(user=user, library=library)
        admin.delete()
    except Admins.DoesNotExist:
        pass
    member.delete()
    return Response({"message": "Member left successfully"})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated, IsLibraryCreator])
def manage_admin(request):
    """Add or remove an admin from a library."""
    library_id = request.data.get("library_id")
    user_id = request.data.get("user_id")
    user = get_object_or_404(User, id=user_id)
    library = get_object_or_404(Libraries, id=library_id)
    admins = Admins.objects.filter(library=library).count()
    if library.creator == user:
        return Response({"error": "You cannot add yourself as an admin"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        if request.method == "POST":
            logger.info("Adding admin user_id=%s to library_id=%s by user=%s", getattr(user, "id", None), getattr(library, "id", None), request.user.username if request.user else None)
            if admins >= 3:
                return Response({"error": "You cannot have more than 3 admins"}, status=status.HTTP_400_BAD_REQUEST)
            Admins.objects.get_or_create(user=user, library=library)
            message = "Admin added successfully"
        else:
            logger.info("Removing admin user_id=%s from library_id=%s by user=%s", getattr(user, "id", None), getattr(library, "id", None), request.user.username if request.user else None)
            admin = get_object_or_404(Admins, user=user, library=library)
            admin.delete()
            message = "Admin removed successfully"
    except Exception as e:
        logger.exception("manage_admin failed: %s", e)
        message = str(e)

    return Response({"message": message})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated, IsLibraryCreatorOrAdmin])
def manage_course(request):
    """Add or remove a course from a library."""
    if request.method == "POST":
        logger.info("create_course called by user=%s data=%s", request.user.username if request.user else None, request.data)
        return CourseService.create_course(request)
    return CourseService.delete_course(request)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsLibraryCreatorOrAdmin])
def add_document(request):
    """Add a document to a course."""
    logger.info("add_document called by user=%s files=%s data=%s", request.user.username if request.user else None, request.FILES.keys(), request.data)
    return DocumentService.add_document(request)
        

@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsLibraryCreatorOrAdmin])
def delete_document(request):
    logger.info("delete_document called by user=%s data=%s", request.user.username if request.user else None, request.data)
    return DocumentService.delete_document(request)
        

@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsLibraryCreator])
def delete_library(request):
    library_id = request.data.get("library_id")
    library = get_object_or_404(Libraries, id=library_id)
    library.delete()
    return Response({"message": f"{library.library_name} has been deleted"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_libraries(request):
    """Get all libraries."""
    libraries = Libraries.objects.filter(Q(members__user=request.user) 
                                         | Q(creator=request.user, joinable=True)).distinct()
    user_library = Libraries.objects.get(creator=request.user, joinable=False)
    
    response = {
        "header": "Libraries",
        "user": LibrariesSerializer(user_library).data,
        "body": LibrariesSerializer(libraries, many=True).data,
        "active": True
    }
    return Response(response)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def get_courses(request, id):
    """Get all courses for a library."""
    library = get_object_or_404(Libraries, id=id)
    courses = Courses.objects.filter(library=library)
    serializer = CoursesSerializer(courses, many=True)
    response = {
        "header": LibrariesSerializer(library).data,
        "header_active": True,
        "body": serializer.data,
        "active": has_edit_permission(request.user, library),
    }
    logger.info("get_courses for library_id=%s by user=%s", id, request.user.username if request.user else None)
    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def get_documents(request, id):
    """Get all documents for a course."""
    course = get_object_or_404(Courses, id=id)
    documents = Documents.objects.filter(course=course)
    library_id = request.query_params.get("library_id")
    library = get_object_or_404(Libraries, id=library_id)
    serializer = DocumentsSerializer(documents, many=True)
    response = {
        "permission": has_edit_permission(request.user, library),
        "data": serializer.data
    }
    logger.info("get_documents for course_id=%s by user=%s", id, request.user.username if request.user else None)
    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def get_members(request):
    """Get all members for a library."""
    library_id = request.query_params.get("library_id")
    library = get_object_or_404(Libraries, id=library_id)
    admins = Admins.objects.filter(library=library)
    admin_serializer = MembersSerializer(admins, many=True)
    members = Members.objects.filter(library=library)
    member_serializer = MembersSerializer(members, many=True)

    response = {
        "header": "Admins",
        "header_active" : is_creator(request.user, library),
        "sub_header": library.entry_key,
        "body": admin_serializer.data,
        "members": member_serializer.data,
        "active": False,
        "creator": is_creator(request.user, library),
    }
    logger.info("get_members for library_id=%s by user=%s", library_id, request.user.username if request.user else None)
    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def query_llm(request):
    """This function is used to query the LLM."""
    serializer = QueryLLMSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    query = serializer.validated_data["query"]
    course_id = serializer.validated_data["course_id"]

    course, documents = CourseService.get_documents_for_course(course_id)
    document_ids = [d.id for d in documents]
    try:
        logger.info("query_llm called: user=%s course_id=%s query=%s document_count=%s", request.user.username if request.user else None, course_id, query, len(document_ids))
        langraph_service = LangGraphService.get_instance()
        response = langraph_service.get_chain(document_ids, query, course_id, request.user.id)
        logger.info("LLM response generated for user=%s course_id=%s", request.user.username if request.user else None, course_id)
        return Response({"LLM_response": response})
    except (ConnectionError, TimeoutError) as e:
        logger.exception("LLM connection error: %s", e)
        raise LLMServiceError(detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error querying LLM: %s", e)
        raise LLMServiceError(detail="An unexpected error occurred while querying the LLM service.")
    


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def quiz(request):
    """This function is used to generate a quiz."""
    document_id = request.query_params.get("document_id")
    document = get_object_or_404(Documents, id=document_id)
    number_of_questions = request.query_params.get("number_of_questions")
    logger.info("quiz generation requested by user=%s document_id=%s num=%s", request.user.username if request.user else None, document_id, number_of_questions)
    langraph_service = LangGraphService.get_instance()
    response = langraph_service.get_quiz(document.id, number_of_questions)
    logger.info("quiz generated for document_id=%s", document_id)
    return Response(response)