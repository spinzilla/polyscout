# -*- coding: utf-8 -*-
"""生成《Agent-Reach 调研 × PolyScout 影响分析》单文件 HTML。
数据与模板同文件；改数据后重跑：python build_agent_reach_survey.py
产物：../2026-10-08-agent-reach-survey.html（零外部依赖，双击即开）
事实来源：commit 94f06c1 本地精读（2026-10-08），引用见文末清单。
"""
import io, os, sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "2026-10-08-agent-reach-survey.html")

COMMIT = "94f06c1"
REPO = "https://github.com/Panniantong/Agent-Reach"

def blob(path, lines=""):
    return f"{REPO}/blob/{COMMIT}/{path}" + (f"#L{lines}" if lines else "")

# ---------------- 数据 ----------------

META = [
    ("Star / Fork", "93,915 / 8,214", "2026-02-24 创建，约 7 个半月冲到顶流；有赞助商位与营销投放，star 增速含推广成分，不等于代码质量背书"),
    ("活跃度", "极高", "调查当日（2026-10-08）仍有提交；CHANGELOG 逐版本详录根因"),
    ("License / 语言", "MIT / Python 3.10+", "v1.5.0；依赖极轻（requests / feedparser / yt-dlp 等 6 个）"),
    ("测试", "34 个测试文件", "含 cookie 权限、URL 安全、凭据擦除、doctor 凭据边界等安全专项测试"),
    ("定位", "能力层（capability layer）", "负责选型/安装/体检/路由，不做读取本身——读取由 Agent 直接调上游 CLI，无包装层"),
    ("本次调查方式", "只读源码精读", "commit 94f06c1 zipball；未安装、未实跑，实跑结论一律标注"),
]

COMPARE = [
    ("它管什么", "让 Agent「能读到」：选型、安装、体检、后端路由", "让结论「可信」：证据链、逐字引用、provenance、合规宪法、预算熔断"),
    ("核心抽象", "Channel（平台）→ backends 有序候选列表 → active_backend", "Adapter（平台）→ 统一读取层 → Evidence Store 归一化"),
    ("失效应对", "调整列表顺序换代（yt-dlp→bili-cli 实例），doctor 报告当前后端", "目前单 adapter 硬编码，无后端候选与体检概念"),
    ("输出形态", "裸命令输出，Agent 自行解读", "摘录+链接+覆盖率护栏+STALE-SUSPECT 标记"),
    ("合规姿态", "BYO cookie + 专用小号警告；无 robots/ToS 内嵌声明", "合规宪法四条 + 每 adapter 内嵌声明 + 硬预算 20 次/run"),
    ("结论", "不是竞品，是不同层：它是「接入层」，PolyScout 是「证据层」", "可借鉴其接入层机制，不可照搬其「裸调上游」形态（会绕过 Evidence Store）"),
]

ARCH = [
    ("Channel 基类 + 有序后端列表",
     "每个平台一个 Channel，backends[0] 为首选、其余为备选；「换接入方式=调整列表顺序，不是重写代码」。用户可用 <channel>_backend 配置/环境变量强制指定。",
     f"channels/base.py:12-22, 34, 45-59", blob("agent_reach/channels/base.py", "12-22")),
    ("probe_command 四态真实探测",
     "区分 missing / broken / timeout / error——特别识别「stale venv shim」：shutil.which() 找得到但 exec 失败（系统 Python 升级后 pipx 安装断链）。doctor 报的是真实健康度，不是文件存在性。",
     f"probe.py:1-13, 106-110", blob("agent_reach/probe.py", "1-13")),
    ("doctor 一处看全平台",
     "agent-reach doctor --json 输出每平台当前 active_backend 与修复处方；断链后端的处方即使被兜底也会带出。MCP server 只暴露 get_status 一个工具，接口克制。",
     f"integrations/mcp_server.py:1-9, 43-49", blob("agent_reach/integrations/mcp_server.py", "1-9")),
    ("SKILL.md 路由表分发",
     "安装=把 SKILL.md 写进 Agent 的 skills 目录：路由表+常驻规则（动手前先体检、声明在用什么后端、失败按 runbook、顺手 check-update）+ references/*.md 分类命令手册。",
     f"skill/SKILL.md:26-44", blob("agent_reach/skill/SKILL.md", "26-44")),
]

IMPACTS = [
    dict(id="I1", weight=3, tag="直接情报 · B站",
         title="B站后端路线的实证情报：排除 yt-dlp，确认自研 adapter 方向",
         body=[
             "yt-dlp 已被 B站风控全面 412 封死（2026-06 实测：最新版、直连、代理、暖 cookie 全部无效）——PolyScout 若曾把 yt-dlp 列为 B站候选，可彻底排除。",
             "bili-cli 免登录搜索/详情当前可用，但上游 2026-03 起停更（1,068 star，最后 push 2026-03-14）——作为对照信号存在，不宜作为主依赖引入。",
             "其字幕路线是 OpenCLI（复用桌面 Chrome 登录态，29.9k star）；PolyScout 的 BYO SESSDATA + wbi 公开签名路线更轻、无浏览器依赖，且与它同属 BYO 登录态范式——外部选型间接确认 v0.2 路线仍在健康路径上。",
         ],
         action="维持自研 adapter；把「yt-dlp 已死（412，2026-06 实测）」记进项目坑清单；bili-cli 停更信号纳入 B站 adapter 的外部环境监测。",
         refs=[("channels/bilibili.py:1-10, 91-94", blob("agent_reach/channels/bilibili.py", "1-10")),
               ("references/video.md:71-112", blob("agent_reach/skill/references/video.md", "71-112")),
               ("bili-cli 仓库元数据（2026-10-08 API 实测）", "https://github.com/public-clis/bilibili-cli")]),
    dict(id="I2", weight=3, tag="架构借鉴 · v0.3+",
         title="「后端路由 + 真实探测 + doctor」机制：补 PolyScout 的运维层空白",
         body=[
             "PolyScout 现状：单 adapter 硬编码，平台接口变动时只能改代码重发版；无「当前信源健康度」的自检入口。",
             "Agent-Reach 的三件套可直接映射：backends 有序候选列表（换代=调序）、probe_command 四态探测（尤其 stale-venv-shim 识别，Windows 上 pipx/uv 场景高发）、doctor --json 一处汇总各平台 active_backend 与修复处方。",
             "v0.2.1 的字幕覆盖率护栏是「内容质量」维度；它的 probe/doctor 是「信源可达性」维度——两者正交，可合并为 adapter 健康检查的统一设计。",
         ],
         action="v0.3 设计时评估：为 adapter 层增加 check()/doctor 子命令与后端候选抽象（范围先限于探测，不照搬「Agent 裸调上游」——那会绕过 Evidence Store 与预算控制）。",
         refs=[("channels/base.py:12-22", blob("agent_reach/channels/base.py", "12-22")),
               ("probe.py:1-13", blob("agent_reach/probe.py", "1-13")),
               ("mcp_server.py:1-9", blob("agent_reach/integrations/mcp_server.py", "1-9"))]),
    dict(id="I3", weight=2, tag="候选信源 · issue #14 / v0.3",
         title="Exa 与 Jina Reader 进入 websearch / CSDN 候选池（须过合规审）",
         body=[
             "Exa via mcporter：全网语义搜索，MCP 端点免 API key（mcp.exa.ai/mcp）。对应 PolyScout issue #14（websearch adapter 真实 key 未验）的潜在零成本路径——但请求经第三方 MCP 端点，须先确认能纳入 Transport 预算/熔断/取消控制（与 YouTube 准入条件 3 同一条纪律）。",
             "Jina Reader（r.jina.ai）：免费免 key 把任意网页转 Markdown，自带反爬验证页识别（Cloudflare challenge 检测）与 5MB 响应上限。可作为 CSDN adapter（v0.3）与通用网页读取的候选后端——注意它是第三方代理抓取，输出全文 Markdown，须在「摘录+链接永不镜像」宪法下明确：只存摘录、不存全文，落笔后再用。",
             "两者均未在 PolyScout 真实环境验证，按未验项管理。",
         ],
         action="加入 issue #14 与 v0.3 CSDN 的候选池，各补一条合规评估（第三方端点的预算控制 / 全文输出的镜像边界），评估通过前不写代码。",
         refs=[("channels/exa_search.py:21-26", blob("agent_reach/channels/exa_search.py", "21-26")),
               ("channels/web.py:15-31, 48-67", blob("agent_reach/channels/web.py", "48-67"))]),
    dict(id="I4", weight=2, tag="工程细节 · 可立即加固",
         title="凭据处理的工程细节：权限 600、凭据擦除、小号警告文案",
         body=[
             "Cookie/Token 只存 ~/.agent-reach/config.yaml，文件权限 600；错误信息一律经 scrub_url_credentials 擦除后再抛出（含 MCP 层）；配 test_doctor_credential_boundaries / test_cookie_security 等专项测试。",
             "从浏览器提取 cookie 按「最小权限」设计：一次只提取一个明确指定的平台；小红书等只接受用户手工导出（Cookie-Editor），程序不主动读浏览器。",
             "登录态平台的用户警告文案成熟可直接借用：「存在被平台检测并封号的风险，请务必使用专用小号」——与 PolyScout Q5-3（BYO cookie 与 BYOK 同权）配套正合适。",
         ],
         action="B站 SESSDATA 处理对齐：配置文件权限 600 + 错误路径凭据擦除 + README 补专用小号警告（小改动，可随下一版本带上）。",
         refs=[("cookie_extract.py:1-9, 32-57", blob("agent_reach/cookie_extract.py", "1-9")),
               ("mcp_server.py:61-67（scrub_url_credentials 进错误）", blob("agent_reach/integrations/mcp_server.py", "61-67")),
               ("README「Cookie 安全建议」段", f"{REPO}#-cookie-安全建议")]),
    dict(id="I5", weight=1, tag="分发形态 · v0.3 MCP",
         title="Agent-native 分发与 MCP 接口克制设计参考",
         body=[
             "「复制一句话给 Agent 即完成安装」：install.md 本身就是给 Agent 读的执行脚本；SKILL.md 常驻规则（先体检再动手、声明当前后端、失败按 runbook、顺手 check-update）是 Agent 集成文档的成熟模板。",
             "MCP server 只暴露 get_status（doctor 报告）一个工具，不暴露读取——读取留给 Agent 直接调上游。PolyScout v0.3 的 MCP server 定位相反（要暴露带证据链的读取），但其「接口面最小化 + 错误凭据擦除」的写法值得照抄。",
         ],
         action="v0.3 MCP server 与 skill 文档设计时参考其接口克制与常驻规则写法。",
         refs=[("skill/SKILL.md:26-44", blob("agent_reach/skill/SKILL.md", "26-44")),
               ("mcp_server.py:43-49", blob("agent_reach/integrations/mcp_server.py", "43-49"))]),
    dict(id="I6", weight=1, tag="路线参照 · YouTube 封存",
         title="YouTube 现状记录：业界通行做法，但不构成合规证据",
         body=[
             "它用 yt-dlp 走 timedtext 提字幕、音频转写接 groq/openai whisper——代表业界通行现状，但它没有回答 timedtext 合规性问题（PolyScout 准入条件 2），93.9k star 不构成合规背书。",
             "PolyScout YouTube 评估维持 2026-10-05 封存的 5 条准入条件不变；本调研仅作为「业界实践现状」材料归档。",
         ],
         action="无路线变更；该材料归入 YouTube 评估档案。",
         refs=[("channels/youtube.py:42, 96-117", blob("agent_reach/channels/youtube.py", "96-117"))]),
]

RISKS = [
    ("外部 CLI 生态的停更风险不可引入",
     "它的渠道大量依赖第三方单平台 CLI：2026-03 一批集体停更（README 自述「接入方式会换代」），bili-cli 亦已停更。它用「路由层调序」消化这个风险；PolyScout 若直接引入这类依赖则风险进体内。结论：自研 adapter 的重资产路线不变，外部 CLI 只作对照与兜底参照。"),
    ("「Agent 裸调上游」形态与证据链冲突",
     "它读到的内容不进任何证据存储、无 provenance、无预算控制——这正是 PolyScout 的核心差异化。借鉴止于探测/路由层，读取路径必须继续走 Transport + Evidence Store。"),
    ("登录态平台的合规边界",
     "Twitter/小红书/Reddit 等「必须登录态」平台若未来进 PolyScout 路线图，只能走 BYO cookie + 小号警告模式（Q5-3 框架内）；其「专用小号」警告与「不替用户登录、不主动读浏览器 cookie」的边界设定可直接沿用。"),
    ("star 数含营销成分",
     "赞助商位（BrowserAct/腾讯云/CoreClaw/UCloud）与 trendshift 推广存在，93.9k star 不等于代码质量背书；但测试覆盖（34 个测试文件含安全专项）与 CHANGELOG 根因记录本身是实打实的质量信号。"),
]

REFS = [
    ("README.md（定位/B站选型/Cookie 警告）", REPO),
    ("agent_reach/channels/base.py（Channel 基类与后端路由语义）", blob("agent_reach/channels/base.py")),
    ("agent_reach/channels/bilibili.py（yt-dlp 412 实测记录）", blob("agent_reach/channels/bilibili.py")),
    ("agent_reach/probe.py（四态探测）", blob("agent_reach/probe.py")),
    ("agent_reach/channels/web.py（Jina Reader 与反爬页检测）", blob("agent_reach/channels/web.py")),
    ("agent_reach/channels/exa_search.py（Exa via mcporter）", blob("agent_reach/channels/exa_search.py")),
    ("agent_reach/channels/youtube.py（yt-dlp 字幕与转写）", blob("agent_reach/channels/youtube.py")),
    ("agent_reach/skill/SKILL.md（Agent 路由表与常驻规则）", blob("agent_reach/skill/SKILL.md")),
    ("agent_reach/integrations/mcp_server.py（MCP 接口）", blob("agent_reach/integrations/mcp_server.py")),
    ("agent_reach/cookie_extract.py（最小权限 cookie 提取）", blob("agent_reach/cookie_extract.py")),
    ("agent_reach/skill/references/video.md（B站命令手册）", blob("agent_reach/skill/references/video.md")),
    ("CHANGELOG.md（雪球修复等根因记录）", blob("CHANGELOG.md")),
    ("bili-cli 仓库（停更状态核实）", "https://github.com/public-clis/bilibili-cli"),
    ("OpenCLI 仓库（活跃度核实）", "https://github.com/jackwener/OpenCLI"),
]

NOW_WHAT = [
    ("① 采纳进 v0.3 设计", "把「后端候选列表 + probe 四态探测 + doctor 自检」写进 v0.3（CSDN + MCP）设计文档的 adapter 健康检查章节——只取探测层，不取「裸调上游」形态。"),
    ("② 候选池 + 合规审", "Exa（issue #14）、Jina Reader（CSDN/通用网页）进候选池；各补一条合规评估（第三方端点预算控制 / 全文输出的镜像边界），审过再写码。"),
    ("③ B站路线维持", "yt-dlp 已死（412 实证）记进坑清单；自研 adapter + BYO SESSDATA 不变；bili-cli 停更纳入外部监测。"),
]

# ---------------- 模板 ----------------

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1a1d23;--mut:#5b6472;--line:#e3e6eb;
--a:#2563eb;--a2:#eff6ff;--ok:#15803d;--okbg:#f0fdf4;--warn:#b45309;--warnbg:#fffbeb;--bad:#b91c1c;--badbg:#fef2f2}
@media(prefers-color-scheme:dark){:root{--bg:#111418;--card:#1a1f27;--ink:#e6e9ef;--mut:#9aa4b2;--line:#2a3140;
--a:#60a5fa;--a2:#17233a;--ok:#4ade80;--okbg:#12291b;--warn:#fbbf24;--warnbg:#2b2110;--bad:#f87171;--badbg:#2b1515}}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:15px/1.75 "Segoe UI","Microsoft YaHei",system-ui,sans-serif;padding:28px 14px 60px}
.wrap{max-width:780px;margin:0 auto}
h1{font-size:24px;margin-bottom:4px}
.sub{color:var(--mut);font-size:13px;margin-bottom:20px}
h2{font-size:18px;margin:34px 0 12px;padding-left:10px;border-left:4px solid var(--a)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:12px}
.hero{background:var(--a2);border:1px solid var(--a);border-radius:12px;padding:18px 20px;margin-bottom:14px}
.hero h2{border:none;padding:0;margin:0 0 8px;font-size:17px;color:var(--a)}
.hero ol{margin-left:20px}
.hero li{margin-bottom:8px}
.verdict{font-size:16px;font-weight:600;background:var(--okbg);border:1px solid var(--ok);border-radius:12px;padding:16px 18px;margin-bottom:14px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:640px){.grid2{grid-template-columns:1fr}}
.kv{display:flex;gap:10px;padding:9px 0;border-bottom:1px dashed var(--line)}
.kv:last-child{border-bottom:none}
.k{width:110px;flex:none;color:var(--mut);font-size:13px;padding-top:2px}
.v{flex:1;font-weight:600}
.v small{display:block;font-weight:400;color:var(--mut)}
table.cmp{width:100%;border-collapse:collapse;font-size:14px}
table.cmp th,table.cmp td{border:1px solid var(--line);padding:9px 11px;text-align:left;vertical-align:top}
table.cmp th{background:var(--a2);font-size:13px}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:10px;overflow:hidden}
summary{cursor:pointer;padding:13px 16px;font-weight:600;list-style:none;display:flex;align-items:center;gap:10px}
summary::-webkit-details-marker{display:none}
summary .tag{flex:none;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;background:var(--a2);color:var(--a)}
summary .arrow{margin-left:auto;color:var(--mut);transition:transform .15s}
details[open] summary .arrow{transform:rotate(90deg)}
.body{padding:0 16px 14px 16px}
.body ul{margin:6px 0 10px 20px}
.body li{margin-bottom:6px}
.act{background:var(--okbg);border-left:3px solid var(--ok);border-radius:6px;padding:9px 12px;font-size:14px;margin-top:8px}
.act b{color:var(--ok)}
.bar{height:7px;border-radius:99px;background:var(--a);display:inline-block;vertical-align:middle;margin-right:8px}
.wlab{font-size:12px;color:var(--mut)}
.risk{border-left:3px solid var(--warn);background:var(--warnbg);border-radius:6px;padding:10px 13px;margin-bottom:9px;font-size:14px}
.risk b{color:var(--warn)}
a{color:var(--a);text-decoration:none}
a:hover{text-decoration:underline}
.refs{font-size:13.5px}
.refs li{margin-bottom:5px}
.note{font-size:12.5px;color:var(--mut);margin-top:26px;padding-top:12px;border-top:1px solid var(--line)}
code{background:var(--a2);border-radius:4px;padding:1px 5px;font-size:13px}
"""

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def render_now():
    lis = "".join(f"<li><b>{esc(t)}</b>　{esc(d)}</li>" for t, d in NOW_WHAT)
    return f'<div class="hero"><h2>我现在该干什么（PolyScout 视角）</h2><ol>{lis}</ol></div>'

def render_meta():
    rows = "".join(f'<div class="kv"><div class="k">{esc(k)}</div><div class="v">{esc(v)}<small>{esc(n)}</small></div></div>' for k, v, n in META)
    return f'<div class="card">{rows}</div>'

def render_cmp():
    rows = "".join(f"<tr><th style='width:88px'>{esc(k)}</th><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for k, a, b in COMPARE[:-1])
    concl = COMPARE[-1]
    return (f'<div class="card" style="padding:6px 0 0"><table class="cmp">'
            f'<tr><th></th><th style="width:44%">Agent-Reach</th><th>PolyScout</th></tr>{rows}</table>'
            f'<div style="padding:12px 14px"><div class="act"><b>关系判定：</b>{esc(concl[1])}——{esc(concl[2])}</div></div></div>')

def render_arch():
    out = []
    for t, d, src, url in ARCH:
        out.append(f'<div class="card"><b>{esc(t)}</b><p style="margin:6px 0 4px">{esc(d)}</p>'
                   f'<a class="wlab" href="{url}">{esc(src)} ↗</a></div>')
    return "".join(out)

def render_impacts():
    out = []
    for it in IMPACTS:
        bar = f'<span class="bar" style="width:{it["weight"]*22}px"></span><span class="wlab">相关度 {"●"*it["weight"]}{"○"*(3-it["weight"])}</span>'
        lis = "".join(f"<li>{esc(x)}</li>" for x in it["body"])
        refs = "　".join(f'<a class="wlab" href="{u}">{esc(t)} ↗</a>' for t, u in it["refs"])
        out.append(f'''<details><summary><span class="tag">{esc(it["tag"])}</span>{it["id"]}. {esc(it["title"])}<span class="arrow">▶</span></summary>
<div class="body"><div style="padding:8px 0 2px">{bar}</div><ul>{lis}</ul>
<div class="act"><b>对 PolyScout 的动作：</b>{esc(it["action"])}</div>
<div style="margin-top:8px">{refs}</div></div></details>''')
    return "".join(out)

def render_risks():
    return "".join(f'<div class="risk"><b>{esc(t)}：</b>{esc(d)}</div>' for t, d in RISKS)

def render_refs():
    lis = "".join(f'<li><a href="{u}">{esc(t)} ↗</a></li>' for t, u in REFS)
    return f'<ol class="refs">{lis}</ol>'

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent-Reach 调研 × PolyScout 影响分析（2026-10-08）</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>Agent-Reach 调研 × PolyScout 影响分析</h1>
<div class="sub">调查对象：<a href="{REPO}">github.com/Panniantong/Agent-Reach</a> @ commit <code>{COMMIT}</code>（2026-10-08 只读源码精读，未实跑）｜PolyScout v0.2.1 基线</div>

{render_now()}

<div class="verdict">一句话：它不是 PolyScout 的竞品而是「接入层」参照——路线不变（自研 adapter + 证据链不动），值得拿走的是「后端候选路由 + probe 真实探测 + doctor 自检」这套运维层机制，外加两个待合规审的信源候选（Exa / Jina Reader）。</div>

<h2>项目概况</h2>
{render_meta()}

<h2>定位对比：接入层 vs 证据层</h2>
{render_cmp()}

<h2>核心机制（它做对了什么）</h2>
{render_arch()}

<h2>对 PolyScout 的六条影响（按相关度排序）</h2>
{render_impacts()}

<h2>不可照搬项与风险</h2>
{render_risks()}

<h2>引用清单（commit {COMMIT}）</h2>
{render_refs()}

<div class="note">
验证声明：① 本报告全部事实性断言均来自 2026-10-08 对 commit {COMMIT} 的源码精读（zipball 本地解压）与 GitHub REST API 元数据，引用到文件与行号；② 「yt-dlp 被 B站 412 封死」「bili-cli 停更但可用」等为其代码注释/README 自述与仓库元数据，未经 PolyScout 环境独立复现；③ Agent-Reach 本身未安装、未实跑；④ 报告由生成器脚本 build_agent_reach_survey.py 产出，可复现。
</div>
</div></body></html>"""

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)

size = os.path.getsize(OUT)
checks = {
    "details 块数": HTML.count("<details>"),
    "card 块数": HTML.count('class="card"'),
    "引用链接数": HTML.count("href="),
    "risk 块数": HTML.count('class="risk"'),
    "hero 动作数": HTML.count("<li><b>"),
}
print("产物:", os.path.abspath(OUT))
print("字节:", size)
for k, v in checks.items():
    print(f"{k}: {v}")
assert checks["details 块数"] == len(IMPACTS), "影响条目数不符"
assert checks["risk 块数"] == len(RISKS), "风险条目数不符"
print("数据层断言通过")
