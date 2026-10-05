# YouTube adapter 调研底稿（派 Codex 咨询前置调研，2026-10-05）

> 用途：PolyScout 新增 YouTube 信源（「B站的翻版」）的架构咨询输入材料。
> 证据规则：引用均为原文摘录附链接；标注【观测】= 单次观测，【推断】= 需进一步验证。

## 0. 构想一句话

复用 v0.2 B站视频管道（搜索 → 元数据 → CC 字幕优先 → ASR 兜底），新增 YouTube adapter；
新引入项目级 **BYO proxy** 能力（YouTube 在大陆不可直连），代理永不捆绑、永不分发（与 BYOK 同哲学）。

## 1. 搜索/元数据通道：YouTube Data API v3（官方）

- 免费、无付费档、无信用卡要求；配额制而非计费制。
- 配额结构（2026-06-01 起三桶制，Google 官方 quota calculator 原文）：
  > "Projects that enable the YouTube Data API have a default quota allocation of 100 search.list calls,
  > 100 videos.insert calls, and 10,000 units per day combined for all other endpoints."
  > — https://developers.google.com/youtube/v3/determine_quota_cost （转引自 https://outstand.so/blog/youtube-api-pricing-quota）
- 单位成本（多源一致）：`videos.list`/`channels.list`/`playlistItems.list` = 1 unit；
  `search.list` = 100 units（独立桶 100 次/天）；`captions.list` = 50 units；`captions.download` = 200 units。
  — https://ytmoneycalculator.com/blog/youtube-data-api-guide 、https://outstand.so/blog/youtube-api-pricing-quota
- **关键限制**：`captions.download` 仅能下载**视频所有者本人**的字幕（需 OAuth 授权）——
  官方 API 拿不到任意视频的 CC 字幕，第三方视频字幕必须走 timedtext（见 §2）。
- 配额按 Google Cloud project 计；`quotaExceeded` 返回 HTTP 403，重试只会烧第二天的额度（官方 errors 文档，转引自 outstand.so 同文）。
- 含义【推断】：PolyScout 用法（少量 search.list + 批量 videos.list，1 unit/次、可批 50 ID）在免费档内绰绰有余；
  BYO key 与项目 Q6 BYOK 哲学一致。

## 2. 字幕通道：youtube-transcript-api（timedtext，未文档化端点）

- 库现状：MIT，活跃维护，本机 youtube-content 技能已验证可用（Hermes 侧实测）。
- IP 封禁（README「Working around IP bans」原文）：
  > "Unfortunately, YouTube has started blocking most IPs that are known to belong to cloud providers
  > (like AWS, Google Cloud Platform, Azure, etc.) … since YouTube will ban static proxies after extended use,
  > going for rotating residential proxies provide is the most reliable option."
  > — https://github.com/jdepoix/youtube-transcript-api#working-around-ip-bans-requestblocked-or-ipblocked-exception
- 代理支持（README 原文+API）：内置 `WebshareProxyConfig`（`filter_ip_locations` 可按国家限定轮换池）；
  通用 HTTP/HTTPS 代理 CLI 旗标 `--http-proxy / --https-proxy`。
  注意 README 强调 Webshare 必须买 "Residential"，**不要**买 "Proxy Server" 或 "Static Residential"。
- Cookie 认证存在但官方警告（issue 模板原文）：
  > "If you authenticate your requests using cookies, you will be able to continue doing requests for a while.
  > However, YouTube will eventually permanently ban the account that you have used to authenticate with!"
  > — https://github.com/jdepoix/youtube-transcript-api/issues/415
  → 含义：YouTube adapter 必须保持**匿名**，不走 B站 BYO cookie 修订路。
- 维护者自述风险（README Warning 原文）：
  > "This code uses an undocumented part of the YouTube API, which is called by the YouTube web-client.
  > So there is no guarantee that it won't stop working tomorrow."
- 端口分化【观测，2025-12 ~ 2026-01】：YouTube 对 Transcript API（侧栏可搜索转录）加了 attestation 校验，
  TimedText API（CC 字幕）暂未要求；Invidious 字幕功能因此大面积故障，社区 workaround 是改走 TimedText。
  — https://github.com/iv-org/invidious/issues/5571 （limdingwen 2025-12-27 分析，absidue 2026-01-04 确认）
  → 含义【推断】：timedtext 是当前可用窗口，但 attestation 扩散到 TimedText 是真实的中期风险，
  adapter 设计需把「字幕通道可替换」当一等约束。

## 3. 代理方案排序（回答「用户可提供代理，有无更优解」）

| 方案 | 评估 | 证据 |
|---|---|---|
| ① 用户本地代理（Clash/V2ray，住宅宽带 IP） | **黄金标准**，零成本；缺点=绑定本机 | §2 住宅 vs 机房 IP 封禁规律 |
| ② Webshare 轮换住宅代理（文档化推荐给服务端部署用户） | 库内置支持；免费档 5 代理+1GB/月（字幕流量足够）；只买 Residential | §2 README；https://www.evanlin.com/youtube-transcript-proxy |
| ③ Piped 公共实例（无代理用户的降级回退，不做主链路） | 2026-03 约 15 个实例存活；API 有 subtitles 数组（timedtext 代理 URL）；实例列表需动态解析 | https://selfhosting.sh/compare/invidious-vs-piped ；https://docs.piped.video/docs/api-documentation/ |
| ④ 自建 Invidious / CF Worker 中转 | ❌ 排除：前者重运维；CF Worker 出口=机房 IP 必被封 | §2 封禁规律 |
| ⑤ 付费机房代理（datacenter） | ❌ 排除：YouTube 整段封机房 IP | §2 README |

- Invidious 侧证【观测】：公共实例从几十个萎缩到 3~5 个（2026-09 官方清单 5 个 clearnet），
  官方建议「能自托管就别用公共实例」。— https://shortlisted.tools/products/invidious
- 架构含义：代理是 **Transport 层能力**（httpx 支持 proxy 参数），配置走 `POLYSCOUT_PROXY`（per-adapter 可覆盖），
  与宪法 Q5 的关系需 Codex 评估（是否需要像 v0.2 cookie 那样做一轮宪法修订）。

## 4. 法务/合规先例（Apache-2.0 开源分发风险评估）

- youtube-dl 案（2020-10-23 → 2020-11-16）：RIAA 以 DMCA §1201 反规避条款要求 GitHub 下架 youtube-dl；
  EFF 介入后 GitHub **恢复**仓库，结论：未规避有效技术保护措施（视频流本身未加密）；
  GitHub 此后对 §1201 类 claim 一律法律+技术专家人工复核，并设 100 万美元开发者辩护基金。
  — https://github.blog/2020-11-16-standing-up-for-developers-youtube-dl-is-back/ （转引自 xda/wikipedia 多源）
- 边界（sekin.in 分析原文要点）：该恢复**不是法院判决**、不授权一切下载行为、**不凌驾于平台 ToS 之上**、
  不构成全球通行许可。— https://sekin.in/standing-up-for-developers-youtube-dl-is-back-what-githubs-2020-reversal-meant
- 含义【推断】：PolyScout 的暴露面**远小于** youtube-dl——不下载视频/音频流本体（ASR 兜底除外，见下）、
  只输出摘录+链接（宪法 Q5-1）、不绕过任何技术保护措施（CC 字幕是公开端点）。
  风险点主要在 YouTube ToS 层面（民事/合同层面，非刑事/版权层面），合规声明需如实写明 ToS 立场。
  ASR 兜底需要下载音频流（yt-dlp），这是暴露面最大的单点——是否保留、如何限定，需 Codex 评估。

## 5. 现有家底复用点（本机 Hermes 侧已验证）

- youtube-content 技能：`youtube-transcript-api` 已在 Hermes venv 跑通（字幕抓取→摘要全链）。
- v0.2 B站管道（在建）：`excerpt_kind="subtitle_excerpt"` 已入 models.py；faster-whisper ASR 为可选依赖
  `polyscout[asr]` 模式已定型；BYO 登录态宪法修订已有先例（bilibili SESSDATA）。
- 项目定位收益：Q1「面向全球 agent 生态」目前信源全是中国平台，YouTube 是让英文 README 名副其实的拼图。

## 6. 待 Codex 回答的问题清单（已回答，见 §7）

（原 7 问已由 Codex 咨询报告回答，全文见 `2026-10-05-youtube-adapter-codex-consult.md`。）

## 7. 决策记录（2026-10-05，用户：全盘接受 Codex 咨询结论）

**YouTube 列为候选信源，版本维持原路线图（v0.3 = CSDN + MCP，不插队）。**
满足以下 5 个准入条件后再评估是否启动（Codex 原条件）：

1. 官方搜索与元数据在授权环境中实测通过。
2. 字幕访问边界（timedtext 合规性）有明确结论；若没有，用户明确接受元数据版价值。
3. 第三方依赖（youtube-transcript-api 等）所有网络请求都受预算、熔断和取消控制（不得绕过项目 Transport）。
4. 明确 CSDN、MCP 的新位置及 Q4/Q11 修订（若届时决定插队）。
5. 证明相比现有 websearch，它带来可观察的额外证据价值。

**被 Codex 纠正的三个前提**（本底稿上文相应表述以修正为准）：

- §5「ASR 复用」：v0.2 仅做 CC/AI 字幕（Q7 第三轮修订），音频下载与 ASR 已延后单独评审——不存在可直接复用的 ASR 管道。
- §5「定位收益」：Q1 定位是「中文平台穿透引擎」，YouTube 有扩展价值但非必要条件。
- §3「住宅 IP 黄金标准」：证据只支撑「轮换住宅代理最可靠」，推不出用户 Clash 出口稳定可用或「机房 IP 必被封」。

**首版范围（届时若启动）**：官方 Data API 搜索/元数据 + BYO key + BYO 代理（`POLYSCOUT_PROXY` / `POLYSCOUT_YOUTUBE_PROXY`）；
匿名零 cookie；不含 Piped 自动回退、不含音频 ASR；timedtext 字幕须先过合规准入评审。
Q5 需增补代理条款：用户自有代理可作预设路径，碰壁后不得换代理继续访问同一信源。
