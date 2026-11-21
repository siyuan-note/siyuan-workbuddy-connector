---
name: siyuan-skill
description: 思源笔记操作技能 - 搜索、阅读、编写和管理思源笔记的文档、内容块、笔记本、数据库与文件
version: 1.0.0
author: SiYuan
---

# 思源笔记 Skill

思源笔记是一款本地优先的个人知识管理系统。所有操作通过内置的 MCP 服务（Streamable HTTP，端点 `/mcp`）调用，连接器已配置好地址与凭证。用户对工作空间的**所有**笔记本和文档拥有完整权限，写操作会影响真实数据，请谨慎执行。

## 工具总览

MCP 暴露的是**宏工具**：一个工具通过 `action` 参数区分具体子操作（工具描述中列出了全部可用 action 与参数）。以下为常用工具，完整参数以工具的 `description` 与 `inputSchema` 为准。

### search - 搜索

- `fulltext(query, page, pageSize, notebook?, path?, type?, subtype?)`：全文搜索内容块，`notebook` / `path` 为逗号分隔的过滤条件
- `semantic(query, ...)`：语义搜索，需用户已配置 AI embedding
- `asset(query, ...)`：搜索附件文件内容（PDF/Word/Excel/txt 等），返回带 `<mark>` 高亮的片段
- `getasset(path)`：按路径读取单个附件的完整索引内容

### document - 文档生命周期

`list(notebook, parentID?)`、`get(id)`、`info(id)`、`search_docs(keyword)`、`create(notebook, parentID, title, markdown?)`、`rename(id, title)`、`move(id, notebook, parentID)`、`duplicate(id)`、`delete(id)`。

- `get` 只返回元数据和标题，**不含正文**；正文要用 `block.get_kramdown(id)` 或 `export`
- `list` 最多返回 128 个直接子文档，非递归
- 笔记本根目录的 `parentID` 传空字符串 `""`

### block - 内容块

`get(id)`、`get_kramdown(id)`、`get_children(id)`、`tree_stat(id)`、`dom(id)`、`insert(data, dataType, parentID?)`、`append(...)`、`prepend(...)`、`update(id, data, dataType)`、`delete(id)`、`move(id, parentID, previousID?)`、`batch_get(ids)`、`batch_kramdown(ids)`、`breadcrumb(id)`。

- 引用块或裸块 ID 时，先用 `get` / `get_kramdown` 读取内容再回答；锚文本只是预览
- `get` 单字段最多 5120 字符，截断会带 `...`；完整正文用 `get_kramdown`
- `get_children` 的预览截断到 200 字符，需逐 ID 读取
- `update` 是**整体替换**而非增量修改；修改前先 `get_kramdown`，并在 `data` 中保留不需要变更的内容与元数据
- `append` / `prepend` 用于新增子块并返回新 ID；同时"修改+新增"时先 `update` 再 `append`
- 加密笔记本需传入所属 `notebook` ID，其他工具不能绕过权限检查

### sql - 只读 SQL

`schema()` 查看表结构、类型码与拼写示例；`query(stmt)` 执行 SELECT（默认最多 100 行，用 `LIMIT` / `OFFSET` 分页）。用于统计和结构化筛选。前端 SQL 搜索或动态嵌入用 `SELECT b.* FROM blocks b`。加密查询需传 `notebook` 且笔记本已解锁。**不要用 SQL 绕过块工具的笔记本范围或访问错误。**

### notebook - 笔记本

`list()`、`open(id)`、`close(id)`、`create(name)`、`rename(id, name)`、`set_icon(id, icon)`、`random_icon(id?)`、`remove(id)`。

### 其他常用工具

- `attr`：块属性（设置/获取/删除属性、属性视图）
- `tag`：标签管理
- `outline(id)`：文档大纲
- `ref(id)`：引用与反链
- `bookmark`：书签
- `dailynote`：日记
- `database`：属性视图（数据库）。所有子操作通过 `action` 区分：`create` / `search` / `get` / `render` / `keys` / `key_add` / `key_update` / `key_remove` / `item_add` / `item_remove` / `item_update` / `view_get` / `view_add` / `view_update` / `view_remove` / `view_filters_set` / `view_sorts_set` / `view_group_set` / `view_layout_set` 等；修改视图过滤/排序前先 `view_get` 拿到 `revision` 并保留未改动的项
- `export`：导出为 Markdown / HTML / DOCX 等格式
- `import`：导入文件
- `asset` / `image` / `pdf`：附件与图片处理
- `template`：模板渲染
- `history`：历史版本
- `sync`：同步
- `system`：系统信息
- `workspace`：工作空间信息
- `inbox`：收集箱
- `question` / `todo_write` / `memory` / `log` / `mcp` / `decision` / `snippet`：标记为 `AgentOnly`，**不对外部 MCP 暴露**，无需尝试调用

## 使用建议

1. **先定位再读取**：用 `search.fulltext` 或 `document.search_docs` 找到目标，再用 `block.get_kramdown` 读取完整内容。
2. **区分元数据与正文**：`document.get` 不给正文，`batch_get` 只给元数据；`get_kramdown` / `batch_kramdown` 才给内容。
3. **写操作先确认**：创建文档前先 `notebook.list` 确认笔记本 ID；修改块前先读取当前内容。
4. **只读优先**：能用 `sql.query` / `search` 解决的不要写数据；删除文档和笔记本不可撤销。
5. **能力策略**：工作区可配置 MCP 对外暴露的能力，某工具不可用时以实际 `tools/list` 返回为准，不要反复重试。
6. **只读模式 / 加密笔记本**：工作区开启只读模式或笔记本锁定时，对应写操作会被拒绝，需用户先在思源中解除。
