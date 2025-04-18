from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import fitz
import pytesseract
import warnings
from langchain_community.document_loaders import Docx2txtLoader, UnstructuredPowerPointLoader, UnstructuredImageLoader, TextLoader
from langchain.schema import Document
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb
from qdrant_client import QdrantClient
import qdrant_client
from qdrant_client.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue
import uuid

embed_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

#Chroma
chroma_client = chromadb.PersistentClient()
collection = chroma_client.get_or_create_collection(name="documents")

def store_in_chromadb(doc_id: int, docs: Document) -> None:
    texts = [doc.page_content for doc in docs]
    embeddings = embed_model.embed_documents(texts)
    collection.add(
        ids=[f"{doc_id}_{i}" for i in range(len(docs))],
        documents=texts,
        embeddings=embeddings,
        metadatas=[{"text": docs[i].page_content, "id":doc_id} for i in range(len(docs))]
    )

def delete_from_chromadb(doc_id: int) -> None:
    collection.delete(where={"id": {"$eq": doc_id}})


#Qdrant
collection_name = "documents"
def ensure_collection():
    qdrant_client = QdrantClient("http://localhost:6333")
    collections = qdrant_client.get_collections().collections
    if collection_name not in [c.name for c in collections]:
        qdrant_client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )

ensure_collection()

def store_in_qdrant(doc_id: int, docs: Document) -> None:
    
    texts = [doc.page_content for doc in docs]
    embeddings = embed_model.embed_documents(texts)
    client = QdrantClient("http://localhost:6333")
    client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings[i],
                payload={"page_content": docs[i].page_content, "id": doc_id}
            ) for i in range(len(docs))
        ]
    )

def delete_from_qdrant(doc_id: int) -> None:
    client = QdrantClient("http://localhost:6333")
    client.delete(
        collection_name="documents", 
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="id",
                    match=MatchValue(value=doc_id),
                )
            ]
        )
    )


def insert_pdf(file_path: str) -> Document:
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
        for image in page.get_images(full=True):
            xref = image[0]
            pix_pil = fitz.Pixmap(doc, xref).pil_image()
            text_from_image = pytesseract.image_to_string(pix_pil)
            text += text_from_image
    return Document(page_content=text)


def process_file(file_path: str, doc_id: int) -> None:
    file_type = file_path.split(".")[-1].lower()
    if file_type == "docx":
        docs = Docx2txtLoader(file_path).load()

    elif file_type == "pdf":
        docs = insert_pdf(file_path)

    elif file_type == "pptx":
        docs = UnstructuredPowerPointLoader(file_path).load()

    elif file_type in [".png", ".jpg", ".jpeg"]:
        docs = UnstructuredImageLoader(file_path).load()

    elif file_type == "txt":
        docs = TextLoader(file_path, encoding="utf-8").load()

    else:
        raise ValueError("Invalid file type")
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    if file_type == "pdf":
        docs = text_splitter.split_documents([docs])
    else:
        docs = text_splitter.split_documents(docs)

    store_in_qdrant(doc_id, docs)