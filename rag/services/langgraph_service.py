"""RAG retrieval and quiz utilities.

This module contains a thin service layer around the vector store (Qdrant), the
embedder, and the LLM chain used to answer queries and generate quizzes.
"""

from typing import Any, List, Union
import logging

from django.conf import settings
from typing_extensions import TypedDict

from langchain_core.vectorstores.base import VectorStoreRetriever
from langchain_ollama import ChatOllama
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain_qdrant import QdrantVectorStore
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

import sqlite3
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

logger = logging.getLogger(__name__)


class State(TypedDict):
    messages: list  # messages are added to the graph via add_messages


class QuizQuestion(BaseModel):
    question: str = Field(..., description="The quiz question text")
    options: List[str] = Field(..., description="List of 4 multiple choice options")
    answer: str = Field(..., description="The correct option letter (A, B, C, or D)")
    explanation: str = Field(..., description="The explanation of why the answer selected is the correct option")


class QuizOutput(BaseModel):
    quiz: List[QuizQuestion] = Field(..., description="List of generated quiz questions")


class LangGraphService:
    """Service that wires up the embedder, vectorstore, LLM, and graph memory.

    Configurable via Django `settings`:
    - RAG_QDRANT_URL: URL for Qdrant (default: http://localhost:6333)
    - RAG_QDRANT_COLLECTION: collection name (default: "documents")
    - RAG_EMBED_MODEL: huggingface embedder model (default: "all-MiniLM-L6-v2")
    - RAG_OLLAMA_MODEL: model name for Ollama (default: "llama3.2:latest")
    """

    _instance = None

    def __init__(self) -> None:
        ollama_model = getattr(settings, "RAG_OLLAMA_MODEL", "llama3.2:latest")
        embed_model_name = getattr(settings, "RAG_EMBED_MODEL", "all-MiniLM-L6-v2")
        qdrant_url = getattr(settings, "RAG_QDRANT_URL", "http://localhost:6333")
        collection_name = getattr(settings, "RAG_QDRANT_COLLECTION", "documents")

        # LLM
        self.llm = ChatOllama(model=ollama_model, temperature=0.7)

        # Graph persistence / memory
        self.conn = sqlite3.connect(getattr(settings, "RAG_HISTORY_DB", "history.sqlite3"), check_same_thread=False)
        self.memory = SqliteSaver(self.conn)

        # Embedding model and vectorstore
        self.embed_model = HuggingFaceEmbeddings(model_name=embed_model_name)
        self.qdrant_client = QdrantClient(qdrant_url, prefer_grpc=True)
        self.collection_name = collection_name

        # Ensure collection exists
        self.ensure_collection()
        
        self.vectorstore = QdrantVectorStore(
            collection_name=self.collection_name, client=self.qdrant_client, embedding=self.embed_model
        )

        # Parser for quiz output
        self.parser = PydanticOutputParser(pydantic_object=QuizOutput)
        self.format_instructions = self.parser.get_format_instructions()

        

    @classmethod
    def get_instance(cls) -> "LangGraphService":
        """Singleton access to the LangGraphService instance."""
        if cls._instance is None:
            cls._instance = LangGraphService()
        return cls._instance


    def ensure_collection(self) -> None:
        """Create or recreate the collection with a sensible default if it does not exist."""
        try:
            if not self.qdrant_client.collection_exists(self.collection_name):
                logger.info("Creating qdrant collection '%s'", self.collection_name)
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
        except Exception:
            logger.exception("Failed to ensure Qdrant collection '%s'", self.collection_name)
            raise


    def get_retriever(self, document_ids: Union[int, List[int]], k: int = 10, match_type: str = "any") -> VectorStoreRetriever:
        """Return a retriever filtered to the provided document ids.

        document_ids may be a single int or a list of ints. The filter uses
        Qdrant-style `must`/`match` semantics as used by the project.
        """
        if isinstance(document_ids, int):
            ids = [document_ids]
        else:
            ids = list(document_ids)

        search_kwargs = {
            "k": k,
            "filter": {"must": [{"key": "id", "match": {match_type: ids}}]},
        }
        return self.vectorstore.as_retriever(search_kwargs=search_kwargs)
    

    def create_chain(self, prompt: ChatPromptTemplate, retriever: VectorStoreRetriever, llm: ChatOllama) -> RunnableSequence:
        """Build a runnable sequence that takes messages+query and returns an AIMessage.

        The sequence composes the prompt and the RetrievalQA chain used in the
        project.
        """
        return RunnableSequence(
            lambda inputs: {"messages": inputs["messages"], "input": inputs["query"]},
            prompt,
            lambda input_with_prompt: {"query": input_with_prompt.to_string()},
            RetrievalQA.from_chain_type(retriever=retriever, llm=llm, chain_type="stuff", output_key="result"),
            lambda result: AIMessage(content=result["result"]),
        )
    
    
    def get_prompt(self) -> ChatPromptTemplate:
        template = (
            "You are an educational assistant. Answer the question based on the context provided. "
            "If the question seems off-topic, ask for clarification. If it's still off topic then say you can't help. "
            "If the question is not clear, ask for clarification."
        )

        prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages([
            template,
            MessagesPlaceholder(variable_name="messages", optional=True),
            ("user", "{input}"),
        ])
        return prompt


    def chatbot(self, state: State):
        """Graph callable used by the StateGraph - extracts the last user message
        and invokes the RAG chain. Returns a structure compatible with the
        graph's message handling.
        """
        last_user_message = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        # if last_user_message is None:
        #     raise ValueError("No human message found in state.messages")

        inputs = {"messages": state["messages"][:-1], "query": last_user_message.content}
        result = self.rag_chain.invoke(inputs)
        return {"messages": [result]}
    
    
    def stream_graph_updates(self, graph, query: str, config: dict) -> str:
        """Stream graph updates and return the accumulated AI response content.
        This helper unwraps the nested streaming messages produced by the graph.
        """
        response = []
        for message in graph.stream({"messages": [{"role": "user", "content": query}]}, config=config):
            for value in message.values():
                response.append(value)

        # Unwrap first item and return content; allow IndexError to bubble up
        return response[0]["messages"][0].content
    
    
    def get_chain(self, document_ids: List[int], query: str, course_id: int, user_id: int) -> str:
        """Generate a chat response for the given course/user context.

        Args:
            document_ids: list of document ids to use as retriever filter
            query: user query string
            course_id: course identifier used as thread namespace
            user_id: id of user asking the question (used to namespace history)

        Returns:
            AI-generated response text
        """
        thread_id = f"{course_id}_{user_id}"

        retriever: VectorStoreRetriever = self.get_retriever(document_ids)
        prompt: ChatPromptTemplate = self.get_prompt()
        llm: ChatOllama = self.llm

        # Build RAG runnable
        self.rag_chain = self.create_chain(prompt=prompt, retriever=retriever, llm=llm)

        # Build a small graph that calls our chatbot node
        graph_builder: StateGraph = StateGraph(State)
        graph_builder.add_node("chatbot", self.chatbot)
        graph_builder.add_edge(START, "chatbot")
        graph_builder.add_edge("chatbot", END)

        graph = graph_builder.compile(checkpointer=self.memory)
        config = {"configurable": {"thread_id": thread_id}}

        return self.stream_graph_updates(graph, query, config)
    
    
    def get_quiz(self, document_id: int, number_of_questions: int) -> list[dict[str, Any]]:
        """
        Generates quiz questions from a document with robust parsing.
        
        Args:
            query: The topic or prompt for quiz generation
            document_id: ID of the document to use as context
            number_of_questions: Number of questions to generate
            
        Returns:
            List of dictionaries containing questions, answers, and possible answers or error info
        """

        retriever = self.get_retriever(document_id, k=20, match_type="value")
        template = self.get_quiz_template()
        llm = self.llm

        prompt = ChatPromptTemplate.from_template(template).partial(
            format_instructions=self.format_instructions, number=number_of_questions
        )

        qa_chain = self.get_qa_chain(retriever, llm, prompt)
        parser = self.parser

        try:
            response = qa_chain.invoke({"query": "Generate quiz questions"})
            raw_output = response.get("result", "")

            # First attempt: direct parsing
            try:
                parsed = parser.parse(raw_output)
                return [
                    {
                        "question": q.question,
                        "options": q.options,
                        "answer": q.answer,
                        "explanation": q.explanation,
                    }
                    for q in parsed.quiz
                ]
            except Exception:
                # Fallback: try to extract JSON block marked with ```json
                if "```json" in raw_output:
                    try:
                        json_str = raw_output.split("```json")[1].split("```")[0].strip()
                        parsed = parser.parse(json_str)
                        return [
                            {
                                "question": q.question,
                                "options": q.options,
                                "answer": q.answer,
                                "explanation": q.explanation,
                            }
                            for q in parsed.quiz
                        ]
                    except Exception:
                        logger.exception("Failed to parse JSON fenced block from LLM output")

                # Final fallback: raise a helpful error with the raw output
                logger.error("Raw quiz output could not be parsed: %s", raw_output)
                raise ValueError("Failed to parse quiz questions. See server logs for raw LLM output.")

        except Exception:
            logger.exception("Failed to generate quiz questions")
            raise
        

    def get_quiz_template(self) -> str:
        return """Generate exactly {number} quiz questions based on the context below.
    
            FORMATTING INSTRUCTIONS:
            {format_instructions}
            
            CONTEXT:
            {context}
            
            REQUIREMENTS:
            - Each question must have exactly 4 options (A, B, C, D)
            - Specify the correct answer as a single letter (A-D)
            - Output must be valid JSON matching the schema
            - Do include an additional explanation
            
            EXAMPLE OUTPUT:
            {{
                "quiz": [
                    {{
                        "question": "What is the capital of France?",
                        "options": ["London", "Berlin", "Paris", "Madrid"],
                        "answer": "C",
                        "explanation": "Paris is the cultural, economic, and political capital of France. It houses the Elysée Palace (President’s residence), Parliament, and major institutions."
                    }}
                ]
            }}
            
            Now generate {number} questions."""
    

    def get_qa_chain(self, retriever:VectorStoreRetriever, llm:ChatOllama, prompt:ChatPromptTemplate) -> RetrievalQA:
            return RetrievalQA.from_chain_type(
            retriever=retriever,
            llm=llm,
            chain_type_kwargs={
                "prompt": prompt,
                "document_variable_name": "context"
            },
            chain_type="stuff",
            output_key="result"
        )  
