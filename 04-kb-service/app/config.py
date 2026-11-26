"""配置：全部走环境变量，方便 docker / 本机切换。"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---- 基础 ----
    app_name: str = "xiaohui-kb"
    data_dir: Path = Path(os.getenv("KB_DATA_DIR", "./data"))

    # ---- Embedding ----
    # backend: ollama | sentence_transformers | hash
    embed_backend: str = os.getenv("KB_EMBED_BACKEND", "ollama")
    embed_model: str = os.getenv("KB_EMBED_MODEL", "nomic-embed-text")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    embed_dim: int = int(os.getenv("KB_EMBED_DIM", "768"))

    # ---- 向量库 ----
    # backend: qdrant | local（local 用于没起容器时的冒烟测试）
    vector_backend: str = os.getenv("KB_VECTOR_BACKEND", "qdrant")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    collection: str = os.getenv("KB_COLLECTION", "xiaohui_docs")

    # ---- SQLite ----
    sqlite_path: Path = Path(os.getenv("KB_SQLITE", "./data/memory.db"))

    # ---- 切片 ----
    chunk_size: int = int(os.getenv("KB_CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("KB_CHUNK_OVERLAP", "80"))

    # ---- 记忆 ----
    # 可选：调用同学 A 的 LLM 做记忆抽取 / 摘要
    llm_chat_url: str = os.getenv("LLM_CHAT_URL", "")     # 例如 http://127.0.0.1:8000/chat
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "20"))

    def ensure_dirs(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
