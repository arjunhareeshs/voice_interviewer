import logging
import os
import hashlib
from pathlib import Path
from typing import List
from docling.document_converter import DocumentConverter
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

logger = logging.getLogger(__name__)

class ResumeService:
    """
    Handles resume parsing (Docling) and semantic search (nomic-embed-text via Ollama).
    Includes FAISS persistence for faster startup and query caching.
    """
    def __init__(self):
        self.converter = DocumentConverter()
        self.vector_store_dir = Path("vector_store")
        self.vector_store_dir.mkdir(exist_ok=True)
        
        # Query cache to avoid redundant embedding lookups
        self._query_cache = {}
        
        try:
            self.embeddings = OllamaEmbeddings(
                model="nomic-embed-text"
            )
            self.vector_store = None
            self.full_text = ""
        except Exception as e:
            logger.error(f"Failed to load embeddings model: {e}")
            raise

    def _get_resume_hash(self, file_path: str) -> str:
        """Generate hash of resume file for cache validation."""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _get_vector_store_path(self, resume_hash: str) -> Path:
        """Get path for cached vector store."""
        return self.vector_store_dir / f"resume_{resume_hash}"

    def load_resume(self, file_path: str) -> None:
        """Parse resume and create/load embeddings with caching."""
        try:
            logger.info(f"Parsing resume from {file_path}...")
            
            # Calculate resume hash for cache validation
            resume_hash = self._get_resume_hash(file_path)
            vector_store_path = self._get_vector_store_path(resume_hash)
            
            # Try loading from cache first
            if vector_store_path.exists():
                try:
                    logger.info(f"Loading cached embeddings from {vector_store_path}...")
                    self.vector_store = FAISS.load_local(
                        str(vector_store_path),
                        self.embeddings,
                        allow_dangerous_deserialization=True
                    )
                    
                    # Load the resume text from metadata file
                    metadata_path = vector_store_path / "resume_text.txt"
                    if metadata_path.exists():
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            self.full_text = f.read()
                        logger.info("✓ Resume loaded from cache successfully!")
                        return
                except Exception as e:
                    logger.warning(f"Cache load failed: {e}. Regenerating...")
            
            # Parse resume with Docling
            result = self.converter.convert(file_path)
            # Export to markdown to preserve structure (headers, lists)
            self.full_text = result.document.export_to_markdown()
            
            # Split text for embedding with improved parameters
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,      # Larger chunks for better context
                chunk_overlap=200,    # More overlap to prevent boundary issues
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            texts = text_splitter.split_text(self.full_text)
            docs = [Document(page_content=t) for t in texts]
            
            logger.info(f"Split resume into {len(docs)} chunks")
            
            # Create vector store
            logger.info("Generating embeddings...")
            self.vector_store = FAISS.from_documents(docs, self.embeddings)
            
            # Save to disk for future use
            logger.info(f"Saving embeddings to {vector_store_path}...")
            self.vector_store.save_local(str(vector_store_path))
            
            # Save resume text for cache validation
            metadata_path = vector_store_path / "resume_text.txt"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                f.write(self.full_text)
            
            logger.info("✓ Resume loaded and embedded successfully!")
            
        except Exception as e:
            logger.error(f"Error loading resume: {e}")
            raise

    def query_resume(self, query: str, k: int = 3) -> str:
        """
        Retrieve relevant resume sections using semantic search with caching.
        
        Args:
            query: Search query (e.g., "experience", "skills", "education")
            k: Number of chunks to retrieve (default: 3)
            
        Returns:
            Concatenated text of top-k most relevant chunks
        """
        if not self.vector_store:
            logger.warning("Vector store not initialized")
            return ""
        
        # Check cache first to avoid redundant embedding computations
        cache_key = f"{query}:{k}"
        if cache_key in self._query_cache:
            logger.debug(f"Cache hit for query: '{query[:30]}...'")
            return self._query_cache[cache_key]
        
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            result = "\n\n".join([d.page_content for d in docs])
            logger.debug(f"Retrieved {len(docs)} chunks for query: '{query[:50]}...'")
            
            # Cache the result
            self._query_cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Error querying resume: {e}")
            return ""

    def get_full_text(self) -> str:
        return self.full_text
