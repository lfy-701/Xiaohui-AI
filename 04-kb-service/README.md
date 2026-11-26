# kb-service · 知识库与长期记忆

给小慧用的知识库与记忆服务：文档入库、分块、混合检索、长期事实抽取。

## 结构

```text
kb-service/
├── app/
│   ├── main.py      HTTP 接口（文档、检索、记忆、统计）
│   ├── store.py     SQLite 存储层
│   ├── chunk.py     文档切分（句子对齐的重叠切分）
│   ├── keyword.py   关键词检索（jieba BM25 + 中文二元组兜底）
│   ├── embed.py     embedding（hash / ollama / 可选本地模型）
│   ├── memory.py    记忆事实抽取与冲突处理
│   └── config.py    配置
└── requirements.txt
```

## 启动

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8077
```

访问 <http://127.0.0.1:8077/docs>。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `KB_DATA_DIR` | `./data` | 数据目录 |
| `KB_SQLITE` | `./data/memory.db` | SQLite 文件 |
| `KB_VECTOR_BACKEND` | `local` | 向量后端 |
| `KB_EMBED_BACKEND` | `hash` | embedding 方式：`hash` / `ollama` / `sentence-transformers` |

`hash` 方式无需任何外部模型，适合离线与快速启动；需要更好语义召回时切到 ollama。
中文关键词检索始终可用（jieba BM25 + 二元组），作为向量不可用时的兜底。

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/kb/docs` | 上传文档（txt / md / pdf / docx） |
| GET | `/kb/docs` | 文档列表 |
| DELETE | `/kb/docs/{id}` | 删除文档 |
| GET | `/kb/docs/{id}/chunks` | 查看分块结果 |
| GET | `/kb/search?q=` | 混合检索 |
| POST | `/kb/memory/facts` | 写入记忆事实 |
| GET | `/kb/memory/facts` | 读取事实 |
| GET | `/kb/stats` | 统计 |

## 自测

```powershell
python -c "import app.main"
curl.exe "http://127.0.0.1:8077/kb/stats"
```
