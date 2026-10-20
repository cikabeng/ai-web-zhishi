# 知实 AI（EduRAG）

> 高校软件工程实训智能答疑知识库 —— 只基于你上传的课程资料作答，并给出可核对的引用。

当前进度：**P0 骨架完成**（前后端可分别启动、健康检查、配置与跨域、基础测试）。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Pinia |
| 后端 | Python + FastAPI + Pydantic |
| 知识库 | 文档解析 → 分块 → Embedding → ChromaDB（P1 接入） |
| 测试 | pytest（后端）、`vue-tsc` + `vite build`（前端） |

## 目录结构

```
backend/           FastAPI 应用（app/ 代码、tests/ 测试）
frontend/          Vue 3 应用
docs/              设计与环境文档
scripts/           开发脚本
PLAN.md            开发计划（唯一执行依据）
```

## 本地运行

### 1. 后端

```powershell
# 首次：创建虚拟环境并安装依赖（需要网络）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 启动
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- 健康检查：<http://127.0.0.1:8000/api/health>
- 接口文档：<http://127.0.0.1:8000/api/docs>

### 2. 前端

```powershell
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>，前端通过 Vite 代理访问 `/api`，无需额外配置跨域。

### 3. 一键启动

```powershell
.\scripts\dev.ps1
```

## 配置

复制 `.env.example` 为 `.env`（**不要提交**），按需填写：

- `LLM_API_KEY` 留空 → 自动进入**演示模式**：检索真实执行，回答由模板生成，界面上会明确标注。
- `EMBED_PROVIDER` 留空时，配了 `EMBED_API_KEY` 走远程向量模型，否则用本地 `hash` 向量（离线可用、语义能力弱）。

## 测试

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
```
