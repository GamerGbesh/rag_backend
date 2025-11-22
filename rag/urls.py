from django.urls import path
from . import views

urlpatterns = [
    path("createLibrary", views.create_library, name="createLibrary"),
    path("joinLibrary", views.join_library, name="joinLibrary"),
    path("deleteLibrary", views.delete_library, name="deleteLibrary"),
    path("leaveLibrary", views.leave_library, name="leavLibrary"),
    path("deleteDocuments", views.delete_document, name="deleteDocuments"),
    path("removeMember", views.remove_member, name="removeMember"),
    path("admins", views.manage_admin, name="Admins"),
    path("courses", views.manage_course, name="Courses"),
    path("documents", views.add_document, name="Documents"),
    path("libraries", views.get_libraries, name="Libraries"),
    path("course/<int:id>/documents", views.get_documents, name="getDocuments"),
    path("libraries/<int:id>/courses", views.get_courses, name="getCourses"),
    path("getMembers", views.get_members, name="getMembers"),
    path("question", views.query_llm, name="question"),
    path("quiz", views.quiz, name="quiz")
]