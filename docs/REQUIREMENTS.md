# 需求基线（grill 第一轮已冻结，2026-10-03）

设计树方法（grill-me）第一轮六个根决策，用户全部确认：

## Q1 目标用户与定位
面向全球 agent 生态的「中文平台穿透引擎」。英文 README/文档为主，中文为辅。定位词：Break the walls between content platforms。

## Q2 产品形态
Python 包为唯一内核，两个薄入口：pip 库 + CLI、MCP server。**不做托管 Web 服务**（成本/法律/运维三重否定）。

## Q3 开源与许可证
Apache-2.0 开源。理由：专利授权条款、企业敢用、adapter 需要社区贡献。

## Q4 v1 信源范围
①通用网页搜索（Tavily/Bing/兼容 API，基线）②GitHub（官方 REST API）③B站（字幕/ASR 转录，旗舰差异化）④CSDN（尽力而为）。**知乎/公众号 v1 明确不做**，adapter 插件接口留给社区。

## Q5 合规宪法（架构级约束，写进 adapter 开发契约）
1. 输出只有摘录+链接，永不建内容镜像库
2. 硬墙（验证码/风控/登录墙）出现即绕，永不破解；碰壁如实记录
3. 不分发登录态、v1 不支持 cookie 注入
4. 尊重 robots 与平台 ToS，每个 adapter 内嵌合规声明

## Q6 LLM 接入
纯 BYOK：用户自带任意 OpenAI 兼容端点（官方/DeepSeek/中转站/本地 vLLM）。无托管额度、无计费。

## 第二轮已冻结（2026-10-03，用户逐条确认）

- **Q7 B站转录**：官方 CC 字幕优先 + 本地 faster-whisper 兜底；ASR 为可选依赖 `polyscout[asr]`，不进基础安装。
- **Q8 Evidence Store**：JSONL + run 目录约定（evidence.jsonl + report.md + 原始材料），零依赖、纯文本可审计。
- **Q9 调研引擎**：自研轻量规划循环（拆解 → 平台特异化查询词 → 多 adapter 并行 → 综合），零框架依赖；生态位经 MCP server 反向接入。
- **Q10 评测基准**：spike 方法固化为回归评测——固定跨平台题库（≥5 题含 T1-T3）+ 匿名混排 + 双评委盲评脚本；大版本发布前手动跑，不进 CI（评委烧 token）。
- **Q11 发布节奏**：v0.1 = GitHub adapter + 网页搜索 + CLI + Evidence Store（最小可用核）；v0.2 加 B站；v0.3 加 CSDN + MCP。
- **Q12 技术栈**：Python 3.11+ / httpx / pydantic / typer / pytest，无重型框架。
- **Q13 维护承诺**：README 如实写明——学生个人项目 + 社区驱动，issue 响应 best-effort，adapter 健康靠 CI 探针公开看板，不承诺 SLA。

需求基线至此定型（frontier 清空）。下一步：架构设计（issue #2 Adapter 契约、issue #3 Evidence Store schema）。
