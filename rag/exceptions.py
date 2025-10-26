from rest_framework.exceptions import APIException
from rest_framework import status

class LLMServiceError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "LLM service is currently unavailable."
    default_code = "llm_unavailable"