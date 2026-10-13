# TenderBrief

招标要点与目录识别助手。此仓库是独立的新项目；BidMaster 原仓库和目录没有被修改。

## 当前交付

本仓库原先为空。本次建立了可交互的前端开发原型：

- 工作台与 ZIP 选择、拖放
- 大模型配置页（OpenAI 兼容接口）
- Agent 对话工作区
- 汇总信息、商务/技术/价格目录、评分项补充
- 原文证据位置面板和界面样例定位交互
- 空状态、服务失败状态、窄屏适配

界面样例会明确标注为样例数据。未连接 Agent 后端时，页面不会显示文件已上传、模型已保存或真实解析已完成。

## 本地预览

需要 Node.js 18 或更高版本。在 PowerShell 中运行：

    .\start.ps1

浏览器访问 http://127.0.0.1:4173

预览服务器只监听本机回环地址，只对外提供 index.html 和 app.js。Agent API 当前返回 HTTP 501，不会伪装成已接入。

## 后端接口约定

以下真实业务尚未实现：模型配置保存/连接测试、ZIP 上传与解析、Agent 对话、真实证据跳转和 Excel 导出。前端预留了：

- GET /api/health
- POST /api/jobs （multipart 字段 file）
- GET /api/jobs/{job_id}/results
- GET /api/evidence/{evidence_id}
- PUT /api/settings/model
- POST /api/settings/model/test
- POST /api/chat
- PUT /api/jobs/{job_id}/lot （多包任务必须显式选择目标包）

API Key 不写入 localStorage 或 URL。生产环境应由服务端通过 HTTPS 接收并安全存储。

## UI 参考

模型配置参考 Dify 的模型供应商配置页面；文档列表与解析状态参考 RAGFlow 的文档管理流程：
https://github.com/langgenius/dify/blob/main/web/app/components/header/account-setting/model-provider-page/index.tsx
https://github.com/infiniflow/ragflow/blob/main/docs/guides/dataset/files_dataset_document_management.md

TenderBrief 使用自己的标书核对流程、结果区和证据区布局，没有复制上述项目的源码或 UI 组件。
