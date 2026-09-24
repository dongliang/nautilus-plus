# nautilus-plus 项目指南

nautilus(GNOME Files)的定制 fork。上游 C 代码 + `plus/` 目录存放全部 fork 专属内容(文档体系 + Python 扩展)。

本文件是**唯一权威的项目规则**(opencode 的 AGENTS.md)。Claude Code 读 `.claude/CLAUDE.md`、Codex 读 `.codex/AGENTS.md`,两者均为指向本文件的引用,不要在其中复制内容。

## 开工前必读(按顺序)

1. `plus/docs/requirements.md` — 原始需求(短而笼统)
2. `plus/docs/research.md` — 技术调研:已验证机制 / 死路清单 / fork 钩子蓝图 / 架构决策(全部有源码依据)
3. `plus/docs/pitfalls.md` — 踩坑记录(避免重复踩)
4. `plus/docs/CHANGELOG.md` — 版本日志与当前进度
5. `plus/README.md` — 目录结构与 C/Python 分层说明

## 当前状态

- **v0.1.0 已上线**:文件夹描述显示(扩展 `nautilus-meta.py`,字段 `desc`)
- **0.2.0 计划**:分组视图评估——**fork 唯一动机**;开工前先读 `research.md` 第 2 节蓝图

## 已定决策(除非用户明确改变,不要推翻)

1. **显示名覆盖钩子已否决**(2026-08-17)——描述用 caption 第二行方案:真名在上、描述在下。不要重新提议"替换显示名"
2. `.folder.yaml` 是文件夹元数据文件:文件夹内 dotfile(随文件夹移动、工具无关),顶层键 `desc`(字符串)、`archived: true`(布尔,备用)。**改名记录(2026-09-24)**:原名 `.project.yaml`,因用途是通用文件夹元数据而非项目专用、且 `.project.yaml` 与 MuleSoft PDK 的文件重名,改为 `.folder.yaml`;磁盘上的旧文件已一次性迁移,代码不留旧名回退
3. 架构分层:**C 钩子(能力)+ Python 扩展(规则)**;钩子保持"数据源可换"(只认扩展属性,不认写属性者)
4. 扩展已改名 `nautilus-meta.py`(2026-09-25 完成):目录、菜单 ID(`FolderMeta::*`)、配置目录 `~/.config/nautilus-meta/`、类名同步;同日「中文名」概念整体改称「描述」`desc`
5. fork 的 C 改动只服务于分组视图;描述、归档标记全部纯插件可达(扩展 API 已验证)

## 开发约定

- **开工铁律:开发任何功能前,必须先读完「开工前必读」的全部文档**(requirements → research → pitfalls → CHANGELOG),确认已验证的机制与死路后再动手;不能跳过、不能凭印象开工
- **Python 扩展**:改 `plus/extensions/python/nautilus-meta/`;按下方验收流程**本地安装到系统**生效(sudo 不可用时临时装 `~/.local/share/nautilus-python/extensions/`,但系统副本必须删除,两者同存会双菜单——pitfalls #5);改后 `nautilus-plus -q` 重启生效;错误在 nautilus stderr
- **C 改动**:标准 meson 构建(上游约定);`upstream` 远端(GNOME/nautilus)供参考;fork 专属内容只放 `plus/`,不碰上游目录(`docs/`、`extensions/` 是上游的)
- 新功能先写设计文档(`plus/docs/design/`)再动代码
- 环境:nautilus 50.x + nautilus-python 4.1,GI 版本号 `4.1`,依赖 PyYAML

## 每个开发任务的验收环节(必做)

任何 C/Python 改动完成后,必须**本地安装到系统**,再打开 `plus/dev-demo/` 人工验收:

1. **构建**:`meson setup build --prefix=/usr -Dprofile=Plus -Ddocs=false`(prefix 必须为 /usr,见 pitfalls.md 第 12 条;已配置时 `ninja -C build` 增量即可)
2. **本地安装**:`sudo ninja -C build install`(装 `/usr/bin/nautilus-plus` + 扩展 `/usr/share/nautilus-python/extensions/`;sudo 需要密码时请用户在自己终端执行)
3. **打开**:`nautilus-plus plus/dev-demo`(fork 是独立应用 ID,与系统 nautilus 并行不冲突,无需退出系统实例;重启 fork 用 `nautilus-plus -q`)
4. **验收内容**:`plus/dev-demo/` 内容与 `/tmp/opencode/demo` 一致——`alpha-project`(desc + archived)、`beta-project`(仅 desc)、`gamma-project`(仅 archived)、`plain-dir`(无 yaml)、`notes.txt`(普通文件);分别用图标视图和列表视图检查分组/描述显示效果
5. 验收后如无遗留需求可退出窗口,不强制清理

## 安装到系统

- fork 身份安装:`meson setup build --prefix=/usr -Dprofile=Plus -Ddocs=false && ninja -C build && sudo ninja -C build install`,启动 `nautilus-plus`(设计见 `plus/docs/design/plus-identity.md`);新电脑先装依赖(`plus/README.md` 有完整清单)
- **Python 扩展随 install 自动装到 `/usr/share/nautilus-python/extensions/`**(Plus 构建,所有用户生效);开发迭代仍装 `~/.local/share/nautilus-python/extensions/`,两者同存会双菜单(pitfalls #5),系统装后删用户副本