# Imports
import os
from typing import Dict, Any

from youtube_transcript_api import YouTubeTranscriptApi, _errors
from fastapi import HTTPException

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

prompt = PromptTemplate(
    template="""
        You are a helpful assistant.
        Answer ONLY from the provided transcript context.
        Keep your answers brief and to the point.
        If the context is insufficient, say you don't know.
        If the question is not about the video or its content, say "Please ask questions about the video only."
        
        {context}
        Question: {question}
    """,
    input_variables=["context", "question"],
)

parser = StrOutputParser()

# ---- File Helper Functions

def video_dir(store_dir: str, video_id: str) -> str:
    return os.path.join(store_dir, video_id)

def index_path(store_dir: str, video_id: str) -> str:
    return os.path.join(video_dir(store_dir, video_id), "index.faiss")

def disk_has_index(store_dir: str, video_id: str) -> bool:
    return os.path.exists(index_path(store_dir, video_id))

# ---- RAM Cache Helper Functions

def get_from_ram(video_id: str, cache: Dict[str, Any]) -> Any | None:
    return cache.get(video_id)

def put_in_ram(video_id: str, index: Any, cache: Dict[str, Any]) -> None:
    cache[video_id] = index

# Data Ingestion Functions

def fetch_transcript(video_id: str) -> str:
    try:
      ytt_api = YouTubeTranscriptApi()
      transcript_list = ytt_api.fetch(video_id, languages=["en"]).to_raw_data()

      transcript = " ".join(chunk["text"] for chunk in transcript_list)
      return transcript
    
    except _errors.NoTranscriptFound:
        raise HTTPException(
            status_code=404,
            detail="This video doesn’t have English subtitles. Please try another video."
        )

    except _errors.TranscriptsDisabled:
        raise HTTPException(
            status_code=403,
            detail="Captions are disabled for this video. Please try another video."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def load_index_from_disk(store_dir: str, video_id: str) -> Any:
    """Load a previously built vector index from disk."""
    base_dir = video_dir(store_dir, video_id)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = FAISS.load_local(folder_path=base_dir,
                          embeddings=embeddings,
                          allow_dangerous_deserialization=True)
    retriever = vs.as_retriever(search_kwargs={"k": 5})
    return retriever

def build_index_and_persist(store_dir: str, video_id: str) -> Any:
    """Fetch transcript, chunk, embed, build index, write to disk (stub)."""
    os.makedirs(video_dir(store_dir, video_id), exist_ok=True)
    path = video_dir(store_dir, video_id)

    transcript = fetch_transcript(video_id)

    chunks = chunk_text(transcript)

    embeddings = embed_chunks(chunks)

    retriever = build_faiss(chunks, embeddings, path)

    return retriever

def ingest(video_id: str, cache: Dict[str, Any], lock, store_dir):

    idx = get_from_ram(video_id, cache)
    if idx is not None:
        return {"status": "ready", "videoId": video_id, "source": "ram"}


    lock = lock[video_id]
    with lock:

        idx = get_from_ram(video_id, cache)
        if idx is not None:
            return {"status": "ready", "videoId": video_id, "source": "ram"}


        if disk_has_index(store_dir, video_id):
            idx = load_index_from_disk(store_dir, video_id)
            put_in_ram(video_id, idx, cache)
            return {"status": "ready", "videoId": video_id, "source": "disk"}


        idx = build_index_and_persist(store_dir, video_id)
        put_in_ram(video_id, idx, cache)
        return {"status": "ready", "videoId": video_id, "source": "built"}

# RAG Pipeline Functions

def chunk_text(transcript: str):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return splitter.create_documents([transcript])

def embed_chunks(chunks):
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return embeddings

def build_faiss(chunks, embeddings, store_path: str):
    vs = FAISS.from_documents(chunks, embeddings)
    vs.save_local(folder_path=store_path)
    retriever = vs.as_retriever(search_type="similarity", search_kwargs={"k": 4})
    return retriever

def ask_llm(retriever, llm, parser, prompt, question, video_id):
    docs = retriever.invoke(question)
    context_text = "\n\n".join(d.page_content for d in docs)

    result = (prompt | llm | parser).invoke({
        "context": context_text,
        "question": question
    }, config={"metadata": {"video_id": video_id}})

    return result
