from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.db.models import Q
# from django.utils.decorators import async_only_middleware
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
# from asgiref.sync import sync_to_async
from .models import  *
from .permissions import *
from .serializers import *
from .roles import *
from .retrieval_qa import get_chain, get_quiz, get_response
from .doc_add import process_file



# Create your views here.
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_library(request):
    """Create a new library"""
    libraries = Libraries.objects.filter(Q(members__user=request.user) 
                                         | Q(creator=request.user, joinable=True)).distinct().count()
    if libraries >= 2:
        return Response({"error": "You can only have 3 libraries"}, status=status.HTTP_400_BAD_REQUEST)
    serializer = LibrariesSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        serializer.save(creator=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def join_library(request):
    """Join an existing library with an entry key."""
    libraries = Libraries.objects.filter(Q(members__user=request.user) 
                                         | Q(creator=request.user, joinable=True)).distinct().count()
    if libraries >= 2:
        return Response({"error": "You can only have 3 libraries"}, status=status.HTTP_400_BAD_REQUEST)
    serializer = JoinLibrariesSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    library = get_object_or_404(Libraries,
                                 library_name=serializer.validated_data['library_name'],
                                 entry_key=serializer.validated_data['entry_key']
                                 )
    member_count = Members.objects.filter(library=library).count()

    if member_count >= 15:
        return Response({"error": "Library is full"}, status=status.HTTP_400_BAD_REQUEST)    
    if not library.joinable:
        return Response({"message": "Library is not joinable"}, status=status.HTTP_403_FORBIDDEN)
    if library.creator == request.user:
        return Response({"message": "You are the creator of this library"}, status=status.HTTP_400_BAD_REQUEST)
    if library.members.filter(user=request.user).exists():
        return Response({"message": "Already a member of this library"}, status=status.HTTP_400_BAD_REQUEST)
    
    
    Members.objects.get_or_create(user=request.user, library=library)
    return Response({"message": "Library joined successfully"})
    

@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsLibraryCreator])
def remove_member(request):
    """Remove a member from a library."""
    library_id = request.data.get("library_id")
    user_id = request.data.get("user_id")
    library = Libraries.objects.get(id=library_id)
    user = User.objects.get(id=user_id)
    member = get_object_or_404(Members, user=user, library=library)
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
    try :
        if request.method == "POST":
            if admins >= 3:
                return Response({"error": "You cannot have more than 3 admins"}, status=status.HTTP_400_BAD_REQUEST)
            Admins.objects.get_or_create(user=user, library=library)
            message = "Admin added successfully"
        else:
            admin = get_object_or_404(Admins, user=user, library=library)
            admin.delete()
            message = "Admin removed successfully"
    except Exception as e:
        message = str(e)
        
    return Response({"message": message})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated, IsLibraryCreatorOrAdmin])
def manage_course(request):
    """Add or remove a course from a library."""
    library_id = request.data.get("library_id")
    library = get_object_or_404(Libraries, id=library_id)

    if request.method == "POST":
        serializer = CoursesSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if Courses.objects.filter(library=library, course_name=request.data.get("course_name")).exists():
            return Response({"error": "Course with this name already exists"}, status=status.HTTP_400_BAD_REQUEST)
        
        courses = Courses.objects.filter(library=library).count()
        if courses >= 3:
            return Response({"error": "You can only have 3 courses per library"}, status=status.HTTP_400_BAD_REQUEST)

        course = serializer.save(library=library)
        return Response({"message": "Course added successfully", "course_id": course.id},status=status.HTTP_201_CREATED)
    
    else:
        course_id = request.data.get("course_id")
        course = get_object_or_404(Courses, id=course_id, library=library)
        course.delete()
        return Response({"message": "Course deleted successfully"})


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsLibraryCreatorOrAdmin])
def add_document(request):
    """Add a document to a course."""
    if "file" not in request.FILES:
        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

    course_id = request.data.get("course_id")
    course = get_object_or_404(Courses, id=course_id)

    documents = Documents.objects.filter(course=course).count()
    if documents >= 5:
        return Response({"error": "You can only have 5 documents per course"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        document = Documents.objects.create(
            user=request.user,
            course=course,
            file=request.FILES["file"],
        )
        process_file(document.file.path, document.id)
        return Response({"message": "File uploaded successfully", 
                         "document":DocumentsSerializer(document).data}, 
                         status=status.HTTP_201_CREATED)
    
    except Exception as e:
        if "document" in locals():
            document.delete()  
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsLibraryCreatorOrAdmin])
def delete_document(request):
    doc_id = request.data.get("doc_id")
    try:
        document = get_object_or_404(Documents, id=doc_id)
        document.delete()
        message = f"{document.file.name} has been deleted"
    except Documents.DoesNotExist:
        message = "The document does not exist"
    return Response({"message": message})
        

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
    # print(get_response())
    response = {
        "header": "Libraries",
        "user": LibrariesSerializer(user_library).data,
        "body": LibrariesSerializer(libraries, many=True).data,
        "active": True
    }
    return Response(response)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def get_courses(request):
    """Get all courses for a library."""
    library_id = request.GET.get("library_id")
    library = get_object_or_404(Libraries, id=library_id)
    courses = Courses.objects.filter(library=library)
    serializer = CoursesSerializer(courses, many=True)
    response = {
        "header": LibrariesSerializer(library).data,
        "header_active": True,
        "body": serializer.data,
        "active": has_edit_permission(request.user, library),
    }
    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def get_documents(request):
    """Get all documents for a course."""
    course_id = request.GET.get("course_id")
    course = get_object_or_404(Courses, id=course_id)
    documents = Documents.objects.filter(course=course)
    library_id = request.GET.get("library_id")
    library = get_object_or_404(Libraries, id=library_id)
    serializer = DocumentsSerializer(documents, many=True)
    response = {
        "permission": has_edit_permission(request.user, library),
        "data": serializer.data
    }
    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def get_members(request):
    """Get all members for a library."""
    library_id = request.GET.get("library_id")
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
    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def query_llm(request):
    """This function is used to query the LLM."""
    query = request.GET.get("query")
    course_id = request.GET.get("course_id")
    course = get_object_or_404(Courses, id=course_id)
    documents = Documents.objects.filter(course=course)
    document_ids = [document.id for document in documents]
    if not query:
        return Response({"error": "Query is required"})
    if not document_ids:
        return Response({"error": "No documents found"})
    if not course:
        return Response({"error": "Course not found"})
    if not documents:
        return Response({"error": "No documents found"})
    try:
        response = get_chain(document_ids, query, course_id, request.user.id)
        return Response({"LLM_response": response})
    except Exception as e:
        return Response({"error": str(e)})
    


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsLibraryMember])
def quiz(request):
    """This function is used to generate a quiz."""
    document_id = request.GET.get("document_id")
    document = get_object_or_404(Documents, id=document_id)
    number_of_questions = request.GET.get("number_of_questions")
    response = get_quiz(document.id, number_of_questions)
    return Response(response)