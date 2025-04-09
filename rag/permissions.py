from rest_framework.permissions import BasePermission
from .models import Libraries, Admins, Members

class IsLibraryCreator(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        library_id = request.data.get("library_id")
        
        if not library_id:
            return False
        
        try:
            library = Libraries.objects.get(id=library_id)
        except Libraries.DoesNotExist:
            return False
        
        return request.user == library.creator
    

class IsLibraryAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        library_id = request.POST.get("library_id")
        if not library_id:
            return False
        
        try:
            library = Libraries.objects.get(id=library_id)
        except Libraries.DoesNotExist:
            return False
        
        return Admins.objects.filter(user=request.user, library=library).exists()
    

class IsLibraryCreatorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            print("User is not authenticated")
            return False

        library_id = request.data.get("library_id")
        if not library_id:
            print("Library ID not provided")
            return False

        try:
            library = Libraries.objects.get(id=library_id)
        except Libraries.DoesNotExist:
            print("Library does not exist")
            return False

        return request.user == library.creator or Admins.objects.filter(user=request.user, library=library).exists()
    

class IsLibraryMember(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.method in ["POST", "DELETE"]:
            library_id = request.data.get("library_id")
        else:
            library_id = request.query_params.get("library_id")
            
        if not library_id:
            return False
        
        try:
            library = Libraries.objects.get(id=library_id)
        except Libraries.DoesNotExist:
            return False

        return Members.objects.filter(user=request.user, library=library).exists() or request.user == library.creator or Admins.objects.filter(user=request.user, library=library).exists()