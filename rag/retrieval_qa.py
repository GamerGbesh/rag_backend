from typing import Any, List, Annotated
from django.conf import settings
from langchain_core.vectorstores.base import VectorStoreRetriever
from typing_extensions import TypedDict
from langchain_ollama import ChatOllama
from langchain.chains import RetrievalQA
# from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain_qdrant import QdrantVectorStore
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
# from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import sqlite3
# import chromadb
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
# from psycopg_pool import AsyncConnectionPool
# from psycopg.rows import dict_row



embed_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
# chroma_client = chromadb.PersistentClient()
qdrant_client = QdrantClient("http://localhost:6333")
collection_name = "documents"


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect("history.sqlite3", check_same_thread=False)

def get_llm() -> ChatOllama:
    return ChatOllama(model="llama3.2:latest", device="cuda", temperature=0.7)

def ensure_collection():
    collections = qdrant_client.get_collections().collections
    if collection_name not in [c.name for c in collections]:
        qdrant_client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )

ensure_collection()

def get_response():
    response = qdrant_client.scroll(
        collection_name=collection_name,
        with_payload=True,
    )
    return response


def get_retriever(document_ids) -> VectorStoreRetriever:
    retriever: VectorStoreRetriever = vectorstore.as_retriever(
        search_kwargs={
                "k": 10,
                "filter": {
                    "must": [
                        {
                            "key": "id",
                            "match": {
                                "any": document_ids  
                            }
                        }
                    ]
                }
        }
    )
    return retriever

def get_prompt() -> ChatPromptTemplate:
    template = """You are an educational assistant. Answer the question based on the context provided. 
                If the questions seems off-topic, ask for clarification. If it's still off topic then say you can't help.
                If the question is not clear, ask for clarification."""
    
    prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages([
        template,
        MessagesPlaceholder(variable_name="messages", optional=True),
        ("user", "{input}")
    ])
    return prompt

# async def ensure_checkpoint_table(conn):
#     await conn.execute("""
#         CREATE TABLE IF NOT EXISTS checkpoints (
#             checkpoint_ns TEXT NOT NULL,
#             checkpoint_id TEXT NOT NULL,
#             state JSONB NOT NULL,
#             PRIMARY KEY (checkpoint_ns, checkpoint_id)
#         );
#     """)
#     await conn.commit()

def create_chain(prompt:ChatPromptTemplate, retriever:VectorStoreRetriever, llm:ChatOllama) -> RunnableSequence:
    return RunnableSequence(
        lambda inputs: {
            "messages": inputs["messages"],
            "input": inputs["query"]
        },
        prompt,
        lambda input_with_prompt: {
            "query": input_with_prompt.to_string()
        },
        RetrievalQA.from_chain_type(
            retriever=retriever,
            llm=llm,
            chain_type="stuff",
            output_key="result",
        ),
        lambda result: AIMessage(content=result["result"]),
    )

vectorstore = QdrantVectorStore(
    collection_name=collection_name,
    client=qdrant_client,
    embedding=embed_model
)

# vectorstore = Chroma(
#     collection_name="documents",
#     client=chroma_client,
#     embedding_function=embed_model
# )


def get_chain(document_ids: list[int], query:str, course_id:int, user_id:int) -> str:
    """
    This deals with generating chat responses when users ask
    """
    thread_id = f"{course_id}_{user_id}"

    class State(TypedDict):
        messages: Annotated[list, add_messages]

    retriever: VectorStoreRetriever = get_retriever(document_ids)
    prompt: ChatPromptTemplate = get_prompt()
    llm: ChatOllama = get_llm()
    
        
    rag_chain = create_chain(prompt=prompt, retriever=retriever, llm=llm)


    def chatbot(state: State):
        last_user_message: HumanMessage | None = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), 
            None
        )
        inputs = {
            "messages": state["messages"][:-1],
            "query": last_user_message.content
        }
        result = rag_chain.invoke(inputs)
        return {"messages": [result]}

    # memory = MemorySaver()
    conn: sqlite3.Connection = get_conn()
    memory = SqliteSaver(conn)

    graph_builder: StateGraph = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_edge("chatbot", END)
    # database = settings.DATABASES["default"]
    # async with AsyncConnectionPool(
    #     conninfo=f"postgres://{database['USER']}:{database['PASSWORD']}@{database['HOST']}:{database['PORT']}/{database['NAME']}",
    #     kwargs={
    #         "autocommit": True,
    #         "prepare_threshold": 0,
    #         "row_factory": dict_row
    #     }
    # ) as pool, pool.connection() as conn:
        # await ensure_checkpoint_table(conn)
    #   memory = AsyncPostgresSaver(conn)


    graph = graph_builder.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": thread_id}}

    def stream_graph_updates():
        response = []
        for message in graph.stream({
            "messages": [{"role": "user", "content": query}]}, config=config):
            for value in message.values():
                response.append(value)

        return response[0]["messages"][0].content

    return stream_graph_updates()
    

def get_quiz(document_id:int, number_of_questions:int) -> dict[str, Any]:
    """
    Generates quiz questions from a document with robust parsing.
    
    Args:
        query: The topic or prompt for quiz generation
        document_id: ID of the document to use as context
        number_of_questions: Number of questions to generate
        
    Returns:
        Dictionary containing questions, answers, and possible answers or error info
    """
    # Define a simpler output schema that's easier for the LLM to generate
    llm: ChatOllama = get_llm()
    class QuizQuestion(BaseModel):
        question: str = Field(description="The quiz question text")
        options: List[str] = Field(description="List of 4 multiple choice options", min_items=4, max_items=4)
        answer: str = Field(description="The correct option letter (A, B, C, or D)")
        explanation: str = Field(description="The explanation of why the answer selected is the correct option")
    
    class QuizOutput(BaseModel):
        quiz: List[QuizQuestion] = Field(description="List of generated quiz questions")

    # Get parser and format instructions
    parser = PydanticOutputParser(pydantic_object=QuizOutput)
    format_instructions = parser.get_format_instructions()

    # Create a very explicit prompt template
    template = """Generate exactly {number} quiz questions based on the context below.
    
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

    prompt = ChatPromptTemplate.from_template(template).partial(
        format_instructions=format_instructions,
        number=number_of_questions,
    )

    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 20, 
            "filter": {
                "must": [
                    {
                        "key": "id",
                        "match": {"value": document_id}
                    }
                ]
            }
        }
    )

    qa_chain = RetrievalQA.from_chain_type(
        retriever=retriever,
        llm=llm,
        chain_type_kwargs={
            "prompt": prompt,
            "document_variable_name": "context"
        },
        chain_type="stuff",
        output_key="result"
    )

    try:
        response = qa_chain.invoke({"query": "Generate quiz questions"})
        raw_output = response["result"]
        
        
        # First try direct parsing
        try:
            parsed = parser.parse(raw_output)
            return [
                {"question": q.question, 
                 "options":q.options, 
                 "answer": q.answer, 
                 "explanation": q.explanation} 
                 for q in parsed.quiz]
        except Exception as parse_error:
            # Fallback: Try to extract JSON from output
            try:
                json_str = raw_output.split("```json")[1].split("```")[0].strip()
                parsed = parser.parse(json_str)
                return [
                {"question": q.question, 
                 "options":q.options, 
                 "answer": q.answer, 
                 "explanation": q.explanation} 
                 for q in parsed.quiz]
            
            except Exception as json_error:
                # Final fallback: Manual extraction
                raise Exception(
                    "Failed to parse quiz questions. Please check the output format."
                ) from json_error
    except Exception as e:
        print(e)
        raise Exception(
            "Failed to generate quiz questions. Please check the input and try again."
        ) from e

    
