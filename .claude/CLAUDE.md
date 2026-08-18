# nautilus-plus 项目指南

nautilus(GNOME Files)的定制 fork。上游 C 代码 + `plus/` 目录存放全部 fork 专属内容(文档体系 + Python 扩展)。

## 开工前必读(按顺序)

1. `plus/docs/requirements.md` — 原始需求(短而笼统)
2. `plus/docs/research.md` — 技术调研:已验证机制 / 死路清单 / fork 钩子蓝图 / 架构决策(全部有源码依据)
3. `plus/docs/pitfalls.md` — 踩坑记录(避免重复踩)
4. `plus/docs/CHANGELOG.md` — 版本日志与当前进度
5. `plus/README.md` — 目录结构与 C/Python 分层说明

## 当前状态

- **v0.1.0 已上线**:name-zh 中文名显示(扩展 `plus/extensions/python/project-name-zh/`)
- **0.2.0 计划**:分组视图评估——**fork 唯一动机**;开工前先读 `research.md` 第 2 节蓝图

## 已定决策(除非用户明确改变,不要推翻)

1. **显示名覆盖钩子已否决**(2026-08-17)——中文名用 caption 第二行方案:英文真名在上、中文别名在下。不要重新提议"替换显示名"
2. `.project.yaml` 是项目元数据文件:文件夹内 dotfile(随文件夹移动、工具无关),顶层键 `name-zh`(字符串)、`archived: true`(布尔,备用)
3. 架构分层:**C 钩子(能力)+ Python 扩展(规则)**;钩子保持"数据源可换"(只认扩展属性,不认写属性者)
4. 扩展文件保持原名 `project-name-zh.py`(改名 `nautilus-meta.py` 列入 0.2.0,需同步菜单 ID 与配置目录)
5. fork 的 C 改动只服务于分组视图;中文名、归档标记全部纯插件可达(扩展 API 已验证)

## 开发约定

- **Python 扩展**:改 `plus/extensions/python/project-name-zh/`;开发装 `~/.local/share/nautilus-python/extensions/`,`nautilus -q` 重启生效;错误在 nautilus stderr
- **C 改动**:标准 meson 构建(上游约定);`upstream` 远端(GNOME/nautilus)供参考;fork 专属内容只放 `plus/`,不碰上游目录(`docs/`、`extensions/` 是上游的)
- 新功能先写设计文档(`plus/docs/design/`)再动代码
- 环境:nautilus 50.x + nautilus-python 4.1,GI 版本号 `4.1`,依赖 PyYAML
