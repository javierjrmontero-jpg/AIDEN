import os
import io
import logging
import chromadb
from chromadb.config import Settings
from fastembed import TextEmbedding
import fitz
from docx import Document as DocxDocument
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes

os.environ["ANONYMIZED_TELEMETRY"] = "False"

logger = logging.getLogger(__name__)

CHROMA_PATH = "/data/vectordb"
os.makedirs(CHROMA_PATH, exist_ok=True)

chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH,
    settings=Settings(anonymized_telemetry=False)
)
embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")

def get_collection(user_id: str):
    return chroma_client.get_or_create_collection(
        name=f"user_{user_id}",
        metadata={"hnsw:space": "cosine"}
    )

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracción inteligente de PDF:
    1. Intenta extraer texto digital directamente
    2. Si el texto es insuficiente, aplica OCR página por página
    3. Combina ambos métodos si es necesario
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    total_pages = len(doc)
    
    # Intentar extracción de texto digital primero
    digital_text = []
    pages_with_text = 0
    
    for page in doc:
        text = page.get_text().strip()
        digital_text.append(text)
        if len(text) > 50:  # Página con contenido real
            pages_with_text += 1
    
    # Si más del 70% de las páginas tienen texto, es un PDF digital
    text_ratio = pages_with_text / total_pages if total_pages > 0 else 0
    
    if text_ratio >= 0.7:
        logger.info(f"PDF digital detectado ({pages_with_text}/{total_pages} páginas con texto)")
        return "\n\n".join(digital_text)
    
    # PDF escaneado o mixto — aplicar OCR
    logger.info(f"PDF escaneado detectado ({pages_with_text}/{total_pages} páginas con texto). Aplicando OCR...")
    
    ocr_text = []
    images = convert_from_bytes(file_bytes, dpi=300)
    
    for i, (image, existing_text) in enumerate(zip(images, digital_text)):
        if len(existing_text) > 50:
            # Esta página ya tiene texto digital — usarlo
            logger.info(f"  Página {i+1}: texto digital ({len(existing_text)} chars)")
            ocr_text.append(existing_text)
        else:
            # Aplicar OCR a esta página
            logger.info(f"  Página {i+1}: aplicando OCR...")
            try:
                # Intentar español primero, luego inglés
                text = pytesseract.image_to_string(
                    image,
                    lang="spa+eng",
                    config="--psm 1 --oem 3"
                )
                ocr_text.append(text.strip())
                logger.info(f"  Página {i+1}: OCR exitoso ({len(text)} chars)")
            except Exception as e:
                logger.error(f"  Página {i+1}: OCR falló: {e}")
                ocr_text.append("")
    
    return "\n\n".join(ocr_text)

def extract_text(file_bytes: bytes, file_type: str) -> str:
    if file_type == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif file_type in ["docx", "doc"]:
        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        return file_bytes.decode("utf-8", errors="ignore")

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def index_document(user_id: str, doc_id: str, filename: str, text: str) -> int:
    chunks = chunk_text(text)
    if not chunks:
        return 0
    collection = get_collection(user_id)
    embeddings = list(embedding_model.embed(chunks))
    collection.add(
        documents=chunks,
        embeddings=[e.tolist() for e in embeddings],
        ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        metadatas=[{"doc_id": doc_id, "filename": filename, "chunk": i} for i in range(len(chunks))]
    )
    return len(chunks)

def search_documents(user_id: str, query: str, n_results: int = 5) -> list:
    try:
        collection = get_collection(user_id)
        if collection.count() == 0:
            return []
        query_embedding = list(embedding_model.embed([query]))[0].tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, collection.count())
        )
        if not results["documents"][0]:
            return []
        return [
            {
                "text": doc,
                "filename": meta["filename"],
                "score": 1 - dist
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )
        ]
    except Exception:
        return []

def delete_document_chunks(user_id: str, doc_id: str):
    try:
        collection = get_collection(user_id)
        ids = [item for item in collection.get()["ids"] if item.startswith(f"{doc_id}_")]
        if ids:
            collection.delete(ids=ids)
    except Exception:
        pass
