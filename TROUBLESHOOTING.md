# TROUBLESHOOTING

常见问题、原因与处理。按"现象 → 原因 → 处理"组织，命令均以 Windows PowerShell 为准。

---

## 1. 启动

### 1.1 `端口被占用`（8000 / 5173）

**现象**：`[Errno 10048] error while attempting to bind on address`，或 Vite 提示端口被占。

**原因**：上一次的服务没关，或别的程序占用。

**处理**：

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -State Listen | Select-Object LocalPort, OwningProcess
Stop-Process -Id <上面的 OwningProcess> -Force
```

或者改端口：后端 `--port 8001`，前端 `--port 5174`（同时把 `vite.config.ts` 的代理改到新端口）。

### 1.2 未找到虚拟环境

**现象**：`scripts\dev.ps1` 提示"未找到虚拟环境"。

**处理**：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 1.3 依赖安装失败

**现象**：`pip install` 卡住、`Errno 13 Permission denied`、`ensurepip returned non-zero`。

**原因**：网络到 PyPI 慢；或在受限环境里临时目录不可写。

**处理**：换国内镜像，并把临时目录指到项目内：

```powershell
$env:TEMP = "$PWD\.tmp"; $env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt `
  --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 1.4 前端 `spawn EPERM` / esbuild 报错

**现象**：`vite build` 或 `npm run dev` 报 `spawn EPERM`。

**原因**：受限环境下无法创建管道式子进程（普通终端不会遇到）。

**处理**：把临时目录指到项目内再执行：

```powershell
$env:TEMP = "$PWD\frontend\.tmp"; $env:TMP = $env:TEMP
npm run dev
```

### 1.5 中文日志乱码

**处理**：设置 `$env:PYTHONUTF8 = '1'`（`scripts\dev.ps1` 已内置）。

---

## 2. 知识库

### 2.1 上传返回 415「只支持 … 格式」

**原因**：扩展名不在白名单（pdf / docx / txt / md）。

**处理**：转成支持格式；注意 `.PDF` 大小写已做兼容，但 `.doc`（旧格式）不支持，请另存为 `.docx`。

### 2.2 上传返回 413「超过上限」

**处理**：改 `.env` 的 `UPLOAD_MAX_MB`（默认 20），或拆分文件。

### 2.3 文档状态是「失败」，错误信息是"没有可提取的文本层"

**原因**：扫描版 PDF（每页都是图片）。

**处理**：先用 OCR 工具转成可复制文本，再上传；或者在截图报错分析里走 OCR 通道（仅适合单张报错图）。

### 2.4 上传成功但检索不到

可能原因与排查顺序：

1. **分数没过阈值**：检索阈值默认 0.15，问法与资料差异太大时会被判为"资料不足"。换个更贴近资料的说法。
2. **索引没建起来**：打开「知识库」，看片段数是否 > 0；为 0 就点「重建」。
3. **查错了文档**：点「预览」确认实际切出来的片段内容。
4. **进程缓存**：重启后端再试（Chroma 客户端按目录缓存）。

### 2.5 删除文档后仍能检索到

**原因**：多半是浏览器缓存了旧回答，或另一个后端进程还在跑。

**处理**：刷新页面；确认只有一个后端进程在跑（`Get-Process python`）。

### 2.6 重复上传同名文件

**行为**：按内容 sha256 去重，内容相同会提示「已存在，跳过重复索引」，不会产生重复向量。内容不同则作为新文档入库。

---

## 3. 教学与问答

### 3.1 点「继续提示」却被压回上一级

**原因**：两种情况

1. **跳级**：一次只能升一级，传更大的层级会被压回（提示"一次只升一级"）。
2. **引导模式下未提交尝试**：进入 L3 前需要在「我的思路/代码」里提交一次内容（提示"需要先提交尝试"）。

**处理**：先提交尝试，或切到「学习模式」。

### 3.2 回答没有引用

**原因**：检索未命中（阈值未过），系统会明确说"没有检索到相关课程资料"。

**处理**：换更具体的说法；或先在知识库上传对应资料。

### 3.3 L4 的例题看起来不像教材

**这是设计**：L4 是系统生成的相似例题，标题明确标注「AI 生成示例 · 非教材原文」，不会冒充教材。

---

## 4. 截图报错分析

### 4.1 返回 503「当前没有可用的 OCR 通道」

**原因**：本地 OCR 依赖没装，且没配置视觉模型。

**处理**：装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install pillow rapidocr-onnxruntime
```

或配置视觉模型（`.env`）：`VLM_BASE_URL` / `VLM_API_KEY` / `VLM_MODEL`，三项齐全即启用。

**兜底**：切到「手动粘贴报错」，功能完全等价。

### 4.2 识别结果缺字/串行

**原因**：截图分辨率低、字体特殊、或长截图滚动拼接。

**处理**：直接编辑识别文本再点「用修正后的内容重新分析」；这是产品设计的容错路径。

### 4.3 行号显示"识别，可能不准"

**这是设计**：OCR 对数字不是零错误，行号一律标记为不确定，接口里 `line_estimated=true`。

### 4.4 返回 413 / 415 / 422

| 状态码 | 含义 | 处理 |
|---|---|---|
| 413 | 图片过大 | 默认上限 8 MB，压缩或截图裁剪 |
| 415 | 格式不支持 | 只支持 PNG / JPEG / WEBP |
| 422 | 图片损坏或无文字 | 换一张清晰截图，或手动粘贴 |

---

## 5. 模型与密钥

### 5.1 当前是演示模式，怎么切到真实模型

```powershell
Copy-Item .env.example .env
# 编辑 .env，填：
# LLM_BASE_URL=https://api.deepseek.com/v1
# LLM_API_KEY=sk-xxx
# LLM_MODEL=deepseek-chat
```

改完**重启后端**，`/api/health` 的 `demo_mode` 变成 false。

> 注意：当前版本的教学提示与错误解释仍由模板生成；接入大模型需要实现调用层（P2）。`demo_mode` 标记用于区分"是否配置了模型"，不代表所有回答都已走模型。

### 5.2 密钥会不会泄露

- 只放在后端 `.env`，`.gitignore` 已排除，前端拿不到；
- `/api/health` 只返回布尔值，不回显任何密钥；
- 提交前可自查：`git grep -n -E "sk-[A-Za-z0-9]{16,}"`。

### 5.3 API 不可用时的降级

**现场模型 API 挂了怎么办**——强制切到演示模式（检索仍然真实执行，界面会显示黄色横幅）：

```powershell
# 方式一：临时环境变量（当前窗口有效）
$env:DEMO_MODE = "on"
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

```ini
# 方式二：写进 .env，永久生效
DEMO_MODE=on
```

改完重启后端，确认：

```powershell
curl.exe -s http://127.0.0.1:8000/api/health
# 期望："demo_mode":true
```

页面顶部会出现「演示模式 · 未配置大模型：检索与引用真实执行，回答由模板生成并已明确标注」的横幅。

- 未配置 Key：自动进入演示模式，检索照常执行；
- 视觉模型调用失败：截图分析返回 422 并提示改用手动粘贴；
- 以上都不影响教学、检索、引用这些核心能力。

---

## 6. 前端

### 6.1 页面白屏

1. 打开浏览器控制台看第一条红色错误；
2. 确认 `npm run dev` 没报错；
3. 确认 `/api/health` 可访问（Vite 代理正常时 `http://localhost:5173/api/health` 也应返回 200）。

### 6.2 请求 502 / 代理失败

**原因**：后端没起，或端口不一致。

**处理**：确认 uvicorn 跑在 8000；检查 `frontend/vite.config.ts` 的 proxy target。

### 6.3 类型检查失败

```powershell
cd frontend
npx vue-tsc --noEmit
```

按报错修；`npm run build` 会先跑类型检查再打包。

---

## 7. 数据重置

想回到干净的初始状态：

```powershell
# 只清知识库（文档 + 向量）
Remove-Item -Recurse -Force storage\library, storage\chroma

# 彻底重置（含上传文件与索引）
Remove-Item -Recurse -Force storage
```

然后重新 `scripts\seed_demo.py`。

---

## 8. 一次性自检

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py     # 导入示例资料
.\.venv\Scripts\python.exe scripts\check_demo.py    # 5 个标准问题
cd backend; ..\.venv\Scripts\python.exe -m pytest -q # 全部单测
cd ..\frontend; npm run build                        # 前端类型检查 + 构建
```

四项都通过，演示环境就是可用的。
