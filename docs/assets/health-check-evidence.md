# 真实模型接入验证证据（脱敏）

> 验证时间：2026-11-16 20:01（ GMT+8 ）
> 验证对象：本仓库（chuan2），后端独立运行于 `:8001`，前端 `:5174`，与另一工作副本完全隔离。
> 用途：技术文档第 4.3 / 6.6 节、演示视频「AI 技术亮点」段落的可核查素材。
> **本文件不含任何密钥、请求头或 `.env` 内容。**

## 1. 健康检查响应（`GET /api/health`）

```json
{
  "status": "ok",
  "name": "知实 AI",
  "version": "0.1.0",
  "env": "dev",
  "demo_mode": false,
  "llm_configured": true,
  "llm_model": "deepseek-chat",
  "embed_provider": "hash",
  "embed_model": "bge-m3",
  "embed_dim": 1024,
  "knowledge_base": {
    "status": "ready",
    "documents": 4,
    "chunks": 15
  },
  "server_time": "2026-11-16T12:01:12.283545Z"
}
```

关键结论：`demo_mode: false` + `llm_configured: true` 说明已退出演示模式、真实模型已接入；知识库 `ready`，4 篇文档 / 15 个片段。

## 2. 真实问答指标（`POST /api/teaching/hint`）

请求体（可复现）：

```json
{"question": "TypeError: can only concatenate str (not \"int\") to str 怎么改？", "target_level": 1}
```

| 指标 | 实测值 |
|---|---|
| HTTP 状态 | 200 |
| 响应耗时 | 4.62 秒 |
| `category` | `error`（编程报错，置信度 0.95） |
| `llm_status` | **`model`**（真实模型生成，非 `template` / `fallback`） |

`model` 是本次验证的核心：说明 L1 提示确实由大模型生成，不是模板，也不是失败后的回退。

## 3. 其他验证基线

| 项目 | 结果 | 命令 |
|---|---|---|
| 后端测试 | 124 passed | `cd backend && ../.venv/Scripts/python.exe -m pytest -q` |
| 演示自检 | 通过 6/6 | `.venv/Scripts/python.exe scripts/check_demo.py` |
| 前端构建 | 通过（vue-tsc 无错） | `cd frontend && npm run build` |
| 前端页面 | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5174/` |

## 4. 口径说明：`embed_dim: 1024` 与实际 512 维

`/api/health` 回显的 `embed_dim: 1024` 来自配置文件 `config.py` 的默认值，是为将来接入远程语义 Embedding 预留的维度；当前实际使用的离线哈希向量由 `backend/app/library/embeddings.py` 的 `EMBED_DIM = 512` 决定。两者并不矛盾：配置是"可调参数"，实现是"当前取值"。技术文档 4.2 与答辩 PPT 均按此口径表述。

## 5. 现场回退预案

模型 API 超时、欠费或不可达时，在根目录 `.env` 中设置 `DEMO_MODE=on` 后重启后端即可一键回到演示模式：检索、引用、分级逻辑全部不受影响，只有回答来源从 `model` 变为 `template`，界面会明确标注。

## 6. 脱敏与合规

- 本仓库 `.gitignore` 排除 `.env`，`git status` 中不含 `.env`；
- `.env.example` 三个 `API_KEY` 项均为空；
- 全仓 `git grep -E "sk-[A-Za-z0-9]{16,}"` 无输出；
- 文档与截图不得出现 Key、请求头、Postman  Authorization 栏或打开的 `.env` 编辑器画面。
