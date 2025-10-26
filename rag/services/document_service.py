import logging
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from ..models import Documents, Courses
from ..serializers import DocumentsSerializer
from .document_utils import process_file

logger = logging.getLogger(__name__)


class DocumentService:
    """Service layer for managing document-related operations."""

    @staticmethod
    def validate_course(course_id):
        """Ensure the course exists."""
        return get_object_or_404(Courses, id=course_id)

    @staticmethod
    def validate_file(file):
        """Ensure a file is provided."""
        if not file:
            raise ValueError("No file provided")

    @staticmethod
    def check_document_limit(course, limit=5):
        """Ensure the course does not exceed the allowed document limit."""
        documents_count = Documents.objects.filter(course=course).count()
        if documents_count >= limit:
            raise ValueError(f"You can only have {limit} documents per course")

    @staticmethod
    @transaction.atomic
    def add_document(request):
        """
        Handle document upload and processing.

        Returns:
            (Response): A DRF Response object.
        """
        try:
            logger.info("add_document called by user=%s files=%s data=%s", request.user.username if request.user else None, request.FILES.keys(), request.data)
            file = request.FILES.get("file")
            DocumentService.validate_file(file)

            course_id = request.data.get("course_id")
            course = DocumentService.validate_course(course_id)

            DocumentService.check_document_limit(course)

            # Create document
            document = Documents.objects.create(user=request.user, course=course, file=file)

            # Process uploaded file
            process_file(document.file.path, document.id)  # type: ignore

            serializer = DocumentsSerializer(document)
            logger.info("File uploaded successfully: document_id=%s user=%s", getattr(document, "id", None), request.user.username if request.user else None)
            return Response({"message": "File uploaded successfully", "document": serializer.data}, status=status.HTTP_201_CREATED)

        except ValueError as e:
            logger.warning("add_document validation error: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("add_document failed: %s", e)
            # Rollback and clean up
            if "document" in locals():
                try:
                    document.delete()
                except Exception:
                    logger.exception("Failed to delete document during rollback: %s", getattr(document, "id", None))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def delete_document(request):
        """
        Handle document deletion.
        """
        doc_id = request.data.get("doc_id")
        document = get_object_or_404(Documents, id=doc_id)
        document_name = document.file.name
        logger.info("delete_document called by user=%s doc_id=%s", request.user.username if request.user else None, doc_id)
        document.delete()
        logger.info("Document deleted: %s (doc_id=%s)", document_name, doc_id)
        return Response({"message": f"{document_name} has been deleted"})
