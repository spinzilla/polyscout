# Agent-Reach 调研 · Codex 独立评审归档（2026-10-08）

- **评审者**：Codex CLI / gpt-6-astra（water555 网关），`--sandbox danger-full-access`，工作目录 `D:\polyscout`
- **消耗**：66,796 tokens；评审方式：静态源码核查（其自报 4 次本地只读命令、0 联网、0 写入、0 测试）
- **评审者自述边界**：仅静态核查；未独立验证快照来源、运行行为或线上状态；PolyScout 当前实现、本次测试组织及新增信源未核查
- **被评材料**：`docs/research/2026-10-08-agent-reach-survey.html`（+ 同源生成器 `scripts/build_agent_reach_survey.py`）；Agent-Reach 源码快照 commit `94f06c1`
- **结论落点**：polyscout-project 技能台账（v0.3 设计输入 / YouTube 外部现状 / B站外部信号三条，2026-10-08 已落）

---

## 1. 事实核查（7 处抽查；路径相对快照根，`A/` = `agent_reach/`）

- **a 部分属实**：`A/channels/bilibili.py:4-9` 记录作者在已尝试配置中遇到 412；没有证明所有环境、未来版本均失效。「全面封死」扩大了证据范围。
- **b 属实，但需修辞**：`A/probe.py:29,106-120` 区分四类失败，另有 `ok`，共五态。能归类失效启动器，但 `broken` 也涵盖其他 `OSError`，不能唯一诊断为旧虚拟环境。
- **c 部分属实**：`A/channels/base.py:45-59` 实现有序候选及 override，但只是置顶，仍允许回退；「强制指定」不准确。调序只能切换已实现的后端。
- **d 部分属实**：`A/channels/exa_search.py:21-34` 确认 mcporter 接入；`README.md:239` 声称免 Key。实现只检查配置，明确不验证远端；当前免 Key、额度和可用性未核查。
- **e 部分属实**：`A/channels/web.py:11-31,48-67` 确有 5 MiB 限制及前 4096 字节验证页检测，但属于 Agent-Reach 本地封装，不是 Jina 服务保证；直接 curl 不会自动继承这些保护。
- **f 属实**：`A/integrations/mcp_server.py:43-49` 只注册 `get_status`。
- **g 部分属实**：`A/cookie_extract.py:224-225,319-326` 限定平台及返回字段；`A/config.py:61-79` 的 600 仅适用于非 Windows。`A/utils/text.py:8-28` 仅擦除特定 URL 凭据，不能覆盖任意 Cookie、SESSDATA。「只存 config.yaml」亦不符：`A/cookie_extract.py:352-403` 存在向其他配置文件同步凭据的路径。

## 2. 六条影响判断

- **I1：过度推断。** 可维持自研，但打回「yt-dlp 已死」。停更仅有上游自述（`A/channels/bilibili.py:91-94`）；最后 push 日期不能证明停止维护，更不能证明自研路线健康。
- **I2：成立，需补前提。** 借鉴诊断机制；区分命令能启动、平台可达、字幕可取。该项目用 `--version` 即判 bili 可用（同文件 84-94），不足以证明业务健康。联网探测也须经过 Transport。
- **I3：成立，仅限候选。** 补服务条款、额度、预算控制及代理转换后逐字证据的保真验证；免 Key 不等于零成本，也不能关闭原接口真实 key 未验的问题。
- **I4：成立，不能照抄。** 应做跨平台权限与完整错误出口脱敏；Windows 需验证访问控制权限。小号警告不替代授权或合规准入。
- **I5：成立，需删自动动作。** 借鉴接口收敛；不要直接采用「顺手查更新」（`A/skill/SKILL.md:41`），以免隐含联网与额外消耗。
- **I6：成立。** 保持封存；「业界通行」证据不足，改为「该项目采用的路线」。

## 3. 盲点与看走眼处

- **健康度被高估**：Web 不联网即返回 `ok`（`A/channels/web.py:43-46`）。建议 doctor 输出探测层级、时间、能力范围，不能只给统一绿灯。
- **结构化诊断值得借鉴**：`A/doctor.py:23-44` 隔离单渠道异常并汇总字段；建议增加格式版本。tier 表示配置门槛（`A/channels/base.py:35`），不是可信度。
- **安装授权比「一句话安装」更重要**：`docs/install.md:15` 明确要求授权后才用 `--system`；这项边界值得保留。
- **定位写得过满**：「不做读取」被 `A/channels/web.py:48-67` 的 `read()` 直接反证。应描述主要定位，避免绝对化。

## 4. 总评（原文）

> 可作为 **v0.3 设计讨论输入，不能作为实现放行证据**。执行 I6；I2–I5 补齐上述前提后采纳；I1 保留风险记录和维持路线建议，打回永久排除结论。PolyScout 当前实现、本次测试组织及新增信源未核查。

---

## 备注

- HTML 报告保持评审时原样（用户 2026-10-08 决定不改 HTML）；修正结论以本文件与技能台账为准——HTML 中 a/b/c/d/e/g 六处表述与 I1 结论按上文修辞降级。
- 派活 prompt 与调用器：`D:\Hermes\_tmp\codex-agent-reach-review\`（临时目录）。
