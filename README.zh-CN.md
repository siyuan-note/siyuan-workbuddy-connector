<p align="center">
<img alt="SiYuan" src="https://b3log.org/images/brand/siyuan-128.png" width="112">
<br><br>
<a title="AGPLv3" href="https://www.gnu.org/licenses/agpl-3.0.txt"><img src="https://img.shields.io/badge/license-AGPLv3-orange.svg?style=flat-square"></a>
<a title="WorkBuddy" href="https://www.workbuddy.cn"><img src="https://img.shields.io/badge/platform-WorkBuddy-4B7BEC.svg?style=flat-square"></a>
<a title="MCP" href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/protocol-MCP-8A63D2.svg?style=flat-square"></a>
</p>

# 思源笔记 WorkBuddy 连接器

思源笔记官方连接器，让 [WorkBuddy](https://www.workbuddy.cn) 通过 Model Context Protocol 读写你的
[思源笔记](https://b3log.org/siyuan/) 工作空间。

[English](README.md)

| | |
|---|---|
| 包名 | `siyuan` |
| 显示名称 | 思源笔记官方连接器 / SiYuan Official Connector |
| 传输方式 | MCP Streamable HTTP，`POST {base}/mcp` |
| 鉴权 | 思源 API token，请求头 `Authorization: Token <token>` |
| 当前版本 | 1.0.3 |
| 最低思源版本 | 3.7.0（该版本开始内置 MCP 服务） |
| 最低 WorkBuddy 版本 | 4.23.0 |
| 许可证 | AGPL-3.0 |

## 能力范围

连接器代理的是思源内核内置的 MCP 工具，读写的是真实工作空间，不是副本：

- **搜索**：全文、语义、附件搜索，也可用只读 SQL 做结构化筛选。
- **读取**：文档、内容块、kramdown 原文、大纲、反链、属性、历史版本。
- **写入**：新建、重命名、移动、复制、删除文档；插入、更新、删除内容块。
- **整理**：笔记本、标签、书签、日记、属性视图（数据库）、模板。
- **搬运**：导出 Markdown / HTML / DOCX，导入文件，管理附件与图片。

写操作会改动真实笔记。加密笔记本、只读模式以及工作空间的 MCP 能力开关依然生效，与在思源中操作一致。

## 安装

1. 在 WorkBuddy 的连接器市场中搜索 **思源笔记 / SiYuan**。
2. 安装 **思源笔记官方连接器**，按下文填写四个字段。
3. 直接对智能体说一句「帮我在思源笔记里搜索关于项目计划的文档」，能返回结果即表示连接成功。

API token 在思源 **设置 → 鉴权 → API token** 中获取。它代表工作空间管理员权限，请像对待密码一样保管。

## 配置项

| 字段 | 含义 | 默认值 | 说明 |
|---|---|---|---|
| `SCHEMA` | 协议 | `http` | 只能填 `http` 或 `https`，不要带 `://`。本机内核填 `http`。 |
| `SIYUAN_HOST` | 主机名或 IP | `127.0.0.1` | **不要带协议、端口和路径。** |
| `SIYUAN_PORT` | 端口 | `6806` | 只填数字。公网 HTTPS 通常填 `443`。 |
| `SIYUAN_API_TOKEN` | API token | — | 思源 **设置 → 鉴权 → API token**。 |

常见组合：

| 场景 | `SCHEMA` | `SIYUAN_HOST` | `SIYUAN_PORT` |
|---|---|---|---|
| 思源与 WorkBuddy 在同一台机器 | `http` | `127.0.0.1` | `6806` |
| 思源在局域网另一台机器 | `http` | `192.168.1.8` | `6806` |
| 反向代理后的公网部署 | `https` | `siyuan.example.com` | `443` |

> 1.0.2 及更早版本把 `host:port` 整体填在 `SIYUAN_HOST` 里，会被客户端的主机名校验拒绝并抛出
> `Invalid hostname variable SIYUAN_HOST`，导致 MCP server 无法注册。1.0.3 起端口独立成字段，
> 详见 [CHANGELOG.md](CHANGELOG.md)。

凭证加密保存在本机 WorkBuddy 配置目录（`~/.workbuddy`）中，除你配置的思源地址外不会发往任何地方。

## 仓库结构

```
.
├── connector-meta.json          # 市场元数据：名称、简介、示例、版本号
├── mcp.json                     # MCP server 声明，URL 使用 ${VAR} 模板
├── token-schema.json            # 连接表单：SCHEMA / SIYUAN_HOST / SIYUAN_PORT / SIYUAN_API_TOKEN
├── icon.svg                     # 上架图标
├── skills/siyuan/SKILL.md       # Agent 技能：工具总览与使用规则
├── scripts/build.py             # 校验并打包到 dist/
├── scripts/smoke_test.py        # 零依赖的 MCP 握手自检
└── .github/workflows/           # push 时校验，打 tag 时产出 zip
```

`.codebuddy-plugin/plugin.json` 和 `ai.workbuddy/token-schema.json` 由 WorkBuddy 平台在发布时**自动生成**，
不在本仓库中维护，手工修改不会生效。

## 构建

只需要 Python 3.9+ 标准库，无需安装依赖。

```bash
python3 scripts/build.py --check   # 仅校验
python3 scripts/build.py           # 校验并生成 dist/siyuan-connector-<version>.zip
```

压缩包是**扁平结构**：`connector-meta.json` 必须位于压缩包根目录，平台不接受多包一层目录的包。
条目时间戳固定，因此同样的源码每次构建出的 sha256 一致。

## 自检

`scripts/smoke_test.py` 复现 WorkBuddy 连接时执行的握手流程（`initialize` → `notifications/initialized`
→ `tools/list`），零第三方依赖，排查连接问题时可先跑它：

```bash
SIYUAN_API_TOKEN=xxxx python3 scripts/smoke_test.py
python3 scripts/smoke_test.py --url https://siyuan.example.com --token xxxx
python3 scripts/smoke_test.py --url https://siyuan.example.com --token xxxx --insecure
```

```
endpoint https://siyuan.example.com/mcp
server   SiYuan 3.8.11 (MCP 2025-11-25)
session  KC4X5EISEFOWVS3UIPQWSRV7JB
tools    31 available
         asset, attr, bazaar, block, bookmark, dailynote, database, document, ...
OK
```

返回 `401` 说明 token 不对或已被重置；`403` 说明 token 不是管理员 token；`tools 0 available`
说明工作空间的 MCP 能力开关被关掉了。

## 发布新版本

1. 修改 `connector-meta.json` 中的 `version`，并在 [CHANGELOG.md](CHANGELOG.md) 中补一条记录。
2. 提交后打 tag 并推送：

   ```bash
   git tag v1.0.4
   git push origin v1.0.4
   ```

3. `Release` 工作流会校验 tag 与 `connector-meta.json` 的版本是否一致，构建 zip 并挂到 GitHub Release。
4. 在 WorkBuddy 开放平台对**现有条目**使用「更新版本」（不要新建条目），上传
   `dist/siyuan-connector-<version>.zip`，提交审核，审核通过后发布。

## 常见问题

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `MCP server "connector:siyuan" is not registered` | 包解析失败，server 没被注册（清单字段非法、zip 多包了一层目录、某个字段被客户端拒绝） | 确认市场中的版本号，重装；对源码跑 `scripts/build.py --check` |
| `Invalid hostname variable SIYUAN_HOST` | `SIYUAN_HOST` 里带了端口或协议 | 把端口移到 `SIYUAN_PORT`，去掉 `http://`；1.0.3 已修复 |
| `401 Unauthorized` | token 被重置，或复制时带上了空格 | 回到 **设置 → 鉴权 → API token** 重新复制 |
| `403 Forbidden` | token 不是管理员 token，或工作空间对当前客户端只读 | 使用工作空间管理员 token；解除只读/锁定 |
| 连接被拒绝 / 超时 | 内核没启动，或内核只监听回环而 WorkBuddy 在另一台机器 | 启动思源，或把连接器指向真正运行内核的机器 |
| 自签证书报 TLS 错误 | 客户端不信任该证书 | 换成受信任证书；先用 `scripts/smoke_test.py --insecure` 验证链路 |

## 安全说明

- API token 具备工作空间管理员权限，可读写、删除任意笔记。
- 只连接你自己控制的思源实例；只要流量离开本机，就应使用 `https`。
- token 疑似泄露时在思源中重置，并在连接器里更新为新值。
- 安全问题请私下联系维护者，不要开公开 issue。

## 许可证

AGPL-3.0，见 [LICENSE](LICENSE)。
