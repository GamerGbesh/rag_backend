from django.apps import AppConfig


class RagConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rag"

    def ready(self) -> None:
        from .services.langgraph_service import LangGraphService
        LangGraphService.get_instance()  # Initialize singleton instance