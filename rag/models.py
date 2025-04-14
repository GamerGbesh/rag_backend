from django.db import models
from django.conf import settings
import os

from django.core.exceptions import ValidationError
from .doc_add import delete_from_chromadb

class Libraries(models.Model):
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_libraries")
    library_name = models.CharField(max_length=50)
    library_description = models.TextField()
    entry_key = models.CharField(max_length=50, default="")
    joinable = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.library_name
    

class Courses(models.Model):
    course_name = models.CharField(max_length=50)
    course_description = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    library = models.ForeignKey(Libraries, on_delete=models.CASCADE, related_name="courses")  

    def __str__(self):
        return self.course_name
    

def validate_file_size(file):
    if file.size >= settings.MAX_UPLOAD_SIZE:
        raise ValidationError(f"File too large. Size should be less than {settings.MAX_UPLOAD_SIZE / (1024 * 1024)}MB.")

def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1]  
    valid_extensions = settings.FILE_EXTENSIONS
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension.')
    
class Documents(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    course = models.ForeignKey(Courses, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="documents/%Y/%m/%d/", validators=[validate_file_size, validate_file_extension])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
    
    def delete(self, *args, **kwargs):
        self.file.delete()
        delete_from_chromadb(self.id)
        super().delete(*args, **kwargs)


class Admins(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_of")
    library = models.ForeignKey(Libraries, on_delete=models.CASCADE, related_name="admins")

    def __str__(self):
        return f"{self.user.username} - {self.library.library_name}"
    

class Members(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member_of")
    library = models.ForeignKey(Libraries, on_delete=models.CASCADE, related_name="members")

    def __str__(self):
        return f"{self.user.username} - {self.library.library_name}"

