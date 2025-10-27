"""Document processing and Qdrant storage helpers.

This module provides utilities for loading different document types, splitting
them into chunks and storing their embeddings in Qdrant. It is intentionally
lightweight and intended to be called from Django view logic when a file is
uploaded.
"""

from typing import Sequence
import logging
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter
import fitz
import pytesseract
from langchain_community.document_loaders import (
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredImageLoader,
    TextLoader,
)
from langchain.schema import Document
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, FilterSelector
from .langgraph_service import LangGraphService

logger = logging.getLogger(__name__)


_service = LangGraphService.get_instance()
_qdrant_client = _service.qdrant_client
_embed_model = _service.embed_model
_COLLECTION_NAME: str = _service.collection_name


class PDFLoader:
    """Custom PDF loader that extracts text and performs OCR on images."""
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        

    def insert_pdf(self, file_path: str, ocr_if_empty: bool = True) -> Sequence[Document]:
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                page_text = page.get_text()
                text += page_text
                if not page_text and ocr_if_empty:
                    for image in page.get_images(full=True):
                        xref = image[0]
                        try:
                            pix = fitz.Pixmap(doc, xref)
                            pix_pil = pix.pil_image()
                            text += "\n" + pytesseract.image_to_string(pix_pil)
                        except Exception:
                            logger.exception("Failed OCR on page image: %s", file_path)
        return [Document(page_content=text)]
    

    def load(self) -> Sequence[Document]:
        return self.insert_pdf(self.file_path)
    

def store_in_qdrant(doc_id: int, docs: Sequence[Document]) -> None:
    """Embed and upsert document chunks into Qdrant.

    Args:
        doc_id: The application document id to store as payload for each vector
        docs: Sequence of langchain Document objects to embed and store
    """
    try:
        texts = [doc.page_content for doc in docs]
        embeddings = _embed_model.embed_documents(texts)
        _qdrant_client.upsert(
            collection_name=_COLLECTION_NAME,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embeddings[i],
                    payload={"page_content": texts[i], "id": doc_id},
                )
                for i in range(len(docs))
            ],
        )
        logger.info("Upserted %d points for doc_id=%s", len(docs), doc_id)
    except Exception:
        logger.exception("Failed to store document %s in Qdrant", doc_id)
        raise


def delete_from_qdrant(doc_id: int) -> None:
    """Delete all vectors associated with the provided application doc id."""
    try:
        _qdrant_client.delete(
            collection_name=_COLLECTION_NAME,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="id", match=MatchValue(value=doc_id))]
                )
            ),
        )
        logger.info("Deleted vectors for doc_id=%s from Qdrant", doc_id)
    except Exception:
        logger.exception("Failed to delete vectors for doc_id=%s", doc_id)
        raise
    

loaders = {
    "docx": Docx2txtLoader,
    "pptx": UnstructuredPowerPointLoader,
    "png": UnstructuredImageLoader,
    "jpg": UnstructuredImageLoader,
    "jpeg": UnstructuredImageLoader,
    "txt": TextLoader,
    "pdf": PDFLoader,
}


def process_file(file_path: str, doc_id: int) -> None:
    """Load the provided file, split into chunks and store embeddings.

    The function recognises docx, pdf, pptx, png/jpg/jpeg and txt files.
    """
    file_type = file_path.split(".")[-1].lower()

    loader_class = loaders.get(file_type)

    if not loader_class:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    try:
        loader_docs = loader_class(file_path).load()
    except Exception as e:
        logger.exception("Failed to load file: %s", file_path)
        raise ValueError(f"Failed to load file: {e}")

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    docs = text_splitter.split_documents(loader_docs)

    store_in_qdrant(doc_id, docs)