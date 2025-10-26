from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from ..models import Courses, Libraries, Documents
from rest_framework.exceptions import ValidationError
from ..serializers import CoursesSerializer
import logging

logger = logging.getLogger(__name__)


class CourseService:
    MAX_COURSES = 3

    @staticmethod
    def create_course(request):
        library_id = request.data.get("library_id")
        library = get_object_or_404(Libraries, id=library_id)
        logger.info("create_course called by user=%s data=%s", request.user.username if request.user else None, request.data)

        serializer = CoursesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if Courses.objects.filter(library=library, course_name=request.data.get("course_name")).exists():
            logger.warning("create_course: duplicate course name for library_id=%s", library_id)
            return Response({"error": "Course with this name already exists"}, status=status.HTTP_400_BAD_REQUEST)

        course_count = Courses.objects.filter(library=library).count()
        if course_count >= CourseService.MAX_COURSES:
            logger.warning("create_course: max courses reached for library_id=%s", library_id)
            return Response({"error": f"You can only have {CourseService.MAX_COURSES} courses per library"}, status=status.HTTP_400_BAD_REQUEST)

        course = serializer.save(library=library)
        course_id = getattr(course, "id", None)
        logger.info("Course created: course_id=%s library_id=%s", course_id, library_id)
        return Response({"message": "Course added successfully", "course_id": course_id}, status=status.HTTP_201_CREATED)

    @staticmethod
    def delete_course(request):
        library_id = request.data.get("library_id")
        course_id = request.data.get("course_id")
        library = get_object_or_404(Libraries, id=library_id)
        course = get_object_or_404(Courses, id=course_id, library=library)
        logger.info("delete_course requested by user=%s course_id=%s library_id=%s", request.user.username if request.user else None, course_id, library_id)
        course.delete()
        logger.info("Course deleted: course_id=%s", course_id)
        return Response({"message": "Course deleted successfully"})

    @staticmethod
    def get_documents_for_course(course_id: int):
        course = get_object_or_404(Courses, id=course_id)
        documents = Documents.objects.filter(course=course)
        if not documents.exists():
            logger.warning("get_documents_for_course: no documents for course_id=%s", course_id)
            raise ValidationError("No documents found for this course")
        return course, documents