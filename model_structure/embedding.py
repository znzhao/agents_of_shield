
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
import logging
from argostranslate import translate, package
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class EmbeddingModel:
    """
    A class for managing text embeddings and performing similarity search using FAISS.
    Supports storing data with user-defined metadata and filtering search by metadata.
    """

    def __init__(self, model_name: str = 'BAAI/bge-base-en-v1.5'):
        self.model = SentenceTransformer(model_name)
        self.embeddings = []  # Stores all embeddings as a list
        self.data = []        # Stores dicts: {'text': ..., 'metadata': {...}}
        self.index = None     # FAISS index for similarity search

    def encode(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()

    def add(self, items: list[dict]):
        """
        Add new items (dicts with 'text' and 'metadata') and their embeddings to the index.
        Example item: {'text': 'Hello', 'metadata': {'author': 'Bob', 'lang': 'en'}}
        """
        texts = [item['text'] for item in items]
        new_embeddings = self.model.encode(texts)
        self.embeddings.extend(new_embeddings)
        self.data.extend(items)
        emb_array = np.array(self.embeddings).astype('float32')
        dim = emb_array.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatL2(dim)
        self.index.reset()
        self.index.add(emb_array)

    def add_existing(self, items: list[dict], embeddings: list[list[float]]):
        self.embeddings.extend(embeddings)
        self.data.extend(items)
        emb_array = np.array(self.embeddings).astype('float32')
        dim = emb_array.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatL2(dim)
        self.index.reset()
        self.index.add(emb_array)

    def search(self, text: str, top_n: int = None, metadata_filter: dict = None):
        """
        Search for the most similar items to the input text.
        First attempts to translate text from Chinese to English using argostranslate.
        Optionally filter items by metadata before similarity search.
        metadata_filter: dict of key-value pairs to match in item['metadata']
        Returns list of matched items (dicts).
        If top_n is None, returns all matches sorted by similarity.
        """
        # Translate from Chinese to English using Argos Translate
        try:
            from_code = "zh"
            to_code = "en"
            
            # Download and install the zh->en package if not already installed
            package.update_package_index()
            available_packages = package.get_available_packages()
            package_to_install = next(
                filter(
                    lambda x: x.from_code == from_code and x.to_code == to_code,
                    available_packages
                ),
                None
            )
            
            if package_to_install is not None:
                package.install_from_path(package_to_install.download())
            
            # Translate the text from Chinese to English
            text = translate.translate(text, from_code, to_code)
            logging.info(f"Translated text: {text}")
        except Exception as e:
            # If translation fails (e.g. models missing, no network), use original text
            logging.debug(f"Translation failed, using original text: {e}")
            pass
        
        def metadata_match(item_metadata, filter_metadata):
            for k, v in filter_metadata.items():
                item_v = item_metadata.get(k)
                if isinstance(v, list):
                    if not isinstance(item_v, list) or not all(elem in item_v for elem in v):
                        return False
                else:
                    if item_v != v:
                        return False
            return True

        if self.index is None or len(self.embeddings) == 0:
            return []
        # Filter items by metadata if filter is provided
        if metadata_filter:
            filtered_indices = [
                i for i, item in enumerate(self.data)
                if metadata_match(item['metadata'], metadata_filter)
            ]
            if not filtered_indices:
                return []
            emb_array = np.array([self.embeddings[i] for i in filtered_indices]).astype('float32')
            temp_index = faiss.IndexFlatL2(emb_array.shape[1])
            temp_index.add(emb_array)
            query_emb = self.model.encode([text]).astype('float32')
            n_search = len(filtered_indices) if top_n is None else min(top_n, len(filtered_indices))
            _, indices = temp_index.search(query_emb, n_search)
            results = [self.data[filtered_indices[idx]] for idx in indices[0] if idx < len(filtered_indices)]
        else:
            query_emb = self.model.encode([text]).astype('float32')
            n_search = len(self.data) if top_n is None else top_n
            _, indices = self.index.search(query_emb, n_search)
            results = [self.data[idx] for idx in indices[0] if idx < len(self.data)]
        return results

if __name__ == "__main__":
    embedding_model = EmbeddingModel()
    items = [
        {"text": "Hello, how are you?", "metadata": {"author": "Alice", "lang": "en"}},
        {"text": "I am fine, thank you!", "metadata": {"author": "Bob", "lang": "en"}},
        {"text": "What's your name?", "metadata": {"author": "Alice", "lang": "en"}},
        {"text": "My name is Bob.", "metadata": {"author": "Bob", "lang": "en"}},
        {"text": "I am bad at math.", "metadata": {"author": "Alice", "lang": "en"}},
    ]
    embedding_model.add(items)
    query = "I am bad at math?"
    # Search only among items authored by Alice
    top_related = embedding_model.search(query, top_n=5, metadata_filter={"author": "Alice"})
    print(top_related)

    # search in Chinese
    query_zh = "你好，你叫啥名字？"
    top_related_zh = embedding_model.search(query_zh, top_n=5, metadata_filter={"author": "Alice"})
    print(top_related_zh)