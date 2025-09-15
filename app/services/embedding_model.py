import os
import time
from typing import List

from langchain_core.embeddings import Embeddings
from openai import OpenAI
from langchain_openai.embeddings import OpenAIEmbeddings

class EmbeddingModel(Embeddings):
    """
    Wrapper around DashScope embeddings that:
    - Works with LangChain/Qdrant
    - Calls the official OpenAI client (DashScope-compatible) for real embeddings
    - Avoids Qdrant's "dummy_text" auto-check error
    """

    def __init__(self, model_name: str = "text-embedding-v3", batch_size: int = 10):
        self.model_name = model_name
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        self.batch_size = int(batch_size)

        self.model = OpenAIEmbeddings(
            model=model_name,
            base_url=self.base_url,
            openai_api_key=self.api_key,
        )

        # Direct OpenAI client (for stable embedding calls)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def get(self):
        """
        Return the embedding model.
        """
        return self

    def _call_embedding_api(self, inputs: List[str]):
        """
        Single call to the underlying embeddings API. Expects a list of strings.
        Returns list[list[float]].
        """
        # Using the same client usage you already had.
        response = self.client.embeddings.create(
            model=self.model_name,
            input=inputs,
            encoding_format="float"
        )
        return [item.embedding for item in response.data]

    def embed_documents(self, docs: List[str]) -> List[List[float]]:
        """
        Safely embed a list of docs by batching requests to <= self.batch_size.
        Returns embeddings in the same order as docs.
        """
        if not docs:
            return []

        # keep the 'dummy_text' compatibility you had
        if docs == ["dummy_text"]:
            # dimension size: map model_name to dimension if necessary (1024 for v3)
            dim = 1024 if "v3" in self.model_name or "embedding-v3" in self.model_name else 1536
            return [[0.0] * dim]

        embeddings: List[List[float]] = []
        n = len(docs)
        for i in range(0, n, self.batch_size):
            batch = docs[i : i + self.batch_size]
            attempt = 0
            while True:
                try:
                    vecs = self._call_embedding_api(batch)
                    # basic validation
                    if not isinstance(vecs, list) or len(vecs) < 1:
                        raise RuntimeError("Embedding API returned unexpected response")
                    embeddings.extend(vecs)
                    break
                except Exception as exc:
                    attempt += 1
                    if attempt >= 3:
                        # bubble up with context (which batch failed)
                        raise RuntimeError(
                            f"Embedding API failed after {attempt} attempts for batch starting at index {i}"
                        ) from exc
                    # backoff before retrying (linear backoff)
                    time.sleep(0.5 * attempt)

        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """Safe embedding for a single query string."""
        response = self.client.embeddings.create(
            model=self.model_name,
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding