# TenderBrief

TenderBrief 是面向招标材料整理的解析 Agent。它以本地 BidMaster 的 Python 解析管线为底座，在其上增加 TenderBrief 工作台、模型配置、围绕当前任务的问答、目标标包选择，以及面向“投标文件格式”章节的商务/技术目录整理。

## 当前能力

- 上传包含招标公告、招标文件、技术规范书及附件的 ZIP；支持嵌套 ZIP。也可直接上传 DOCX、DOC、PDF、XLSX。
- 解析项目字段、分包字段、评分项、技术/商务要求、章节和表格，并为抽取项保留证据编号、来源文件、页码/段落/表格行及原文片段。
- 以“处理账本”呈现解析完成、排除和待复核的内容，报告缺失、扫描或不支持的材料。
- 从招标文件“投标文件格式/组成”章节整理商务、技术和价格目录；评分项不在目录时，作为有原文评分证据的待核对补充项显示。
- 检出多个标包时，要求选一个作为当前整理目标；字段和评分结果按可确认的包件范围过滤。
- 按目标包下载 Excel 复核表，包含分标/包件汇总、专用资质要求、投标目录和评分项，并附字段状态与证据编号。
- 在界面配置 OpenAI 兼容模型；对当前解析报告提问，并只返回报告中实际存在的证据编号。

## 本地运行

需要 Python 3.10+ 和 Node.js 20+。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\start.ps1
```

打开 `http://127.0.0.1:4173/`。可在模型设置页填写兼容端点、模型名称和 API Key；密钥仅存于服务进程内存，服务重启后需重新填写。生产或跨机器访问时，应使用 HTTPS 反向代理并通过环境变量注入长期配置。

## Docker 部署

```bash
docker build -t tenderbrief:latest .
docker run -d --name tenderbrief --restart unless-stopped \
  -p <服务器内网IP>:4173:4173 \
  -v /opt/tenderbrief/work:/app/work \
  tenderbrief:latest
```

浏览器访问 `http://<服务器内网IP>:4173/`。API 端口只在容器内部监听，解析工作目录挂载到 `/opt/tenderbrief/work`。更新代码后重新构建镜像并重建 `tenderbrief` 容器；这不会操作其它项目容器。

也可直接启动 Python API：

```powershell
python -m bidmaster serve --port 8000
```

## 接口

- `POST /api/jobs`、`GET /api/jobs/{id}/results`：TenderBrief 工作台解析与结果适配。
- `PUT /api/jobs/{id}/lot`：选择当前整理的标包。
- `GET /api/jobs/{id}/summary.xlsx?lot_id=...`：下载当前标包的汇总复核表。
- `GET /api/evidence/{id}`、`GET /api/evidence/{id}/context`：定位证据及其原文上下文。
- `GET/PUT /api/settings/model`、`POST /api/settings/model/test`、`POST /api/chat`：模型配置和任务问答。
- 原始 BidMaster API、MCP 与 A2A 路由仍由 `bidmaster.api.main:app` 提供。

上传单文件最大 200 MB；ZIP 递归展开受 BidMaster 的文件数量、层数和解压体积限制。处理产物写入 `work/`，不会提交到 Git。

## 解析边界

解析输出是待核对候选，不替代人工审查。扫描 PDF 需要另行配置 OCR 服务；老式 DOC 需转换为 DOCX；DOCX 页码在未安装 LibreOffice 时可能只能定位到段落或表格。压缩包内不支持的附件格式会列入待复核账本；按安全策略忽略的可执行/签名附件会标为排除。加密或损坏的压缩包会返回解析错误；无法读取的文档需人工处理。不同招标人对汇总表字段和目录排版可能有差异，未能从原文确认的内容不会补造。

当前目录识别依赖文档标题层级与常见章节名称；导出的 Excel 是标准复核工作簿，在拿到客户原始模板前不承诺版式完全一致。请用代表性招标 ZIP 建立验收样本，并据此扩展字段映射与目录规则。

## 项目来源与许可

TenderBrief 的解析底座来自本地 BidMaster 项目，并保留 BidMaster 的 MIT 许可证与第三方依赖/参考项目说明。复制来的解析代码仍使用 `bidmaster` Python 模块名以减少导入链路变更；发行包名为 `tenderbrief-agent`。
