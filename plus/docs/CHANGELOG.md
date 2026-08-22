# 版本日志

## 0.3.0 — 2026-08-19

**fork 独立身份(nautilus-plus)✅ 已实现**,设计见 `design/plus-identity.md`

- 新增 meson `profile=Plus` 构建:`meson setup build --prefix=/usr -Dprofile=Plus -Ddocs=false`
- 二进制 `nautilus-plus`、Application ID `org.gnome.NautilusPlus`(D-Bus 名互不抢占)
- fork 自有的桌面文件与 metainfo(`plus/desktop/`):显示名 `nautilus-plus` / zh_CN「文件管理器增强版」
- **不安装、不注册 `org.freedesktop.FileManager1`**:fork 不抢系统默认文件管理器角色
- 预览器/搜索提供者/FileOperations2 路径自动带 Plus 后缀(PROFILE 机制),与系统实例无交集
- GSettings schema、libnautilus-extension soname、翻译、stock 扩展与系统共享(内容相同,协作非冲突)
- C 改动:devel CSS 类仅 Devel profile;Plus 时跳过 freedesktop D-Bus(含调用点 NULL 守卫)
- 验证:Plus 与默认两个 profile 均构建通过,21/21 测试全绿,desktop/appdata 校验通过
- 安装(需 root,交互式):`sudo ninja -C build-plus install`;启动 `nautilus-plus`
- **Python 扩展挂进 meson(2026-08-19)**:Plus 构建 `install_data` 装 `project-name-zh.py` 到 `/usr/share/nautilus-python/extensions/`(所有用户生效);新电脑依赖清单与完整安装流程见 `plus/README.md`;系统装后需删 `~/.local/...` 旧副本避免双菜单
- **右键修改中文项目名(2026-08-21)**:单个本地文件夹菜单打开 GTK4 单行编辑窗口,预填已有 `name-zh`;支持缺失 `.project.yaml` 时创建,已有文件按 YAML 节点位置局部更新并原子写回,保留其他字段与注释;清空输入确认 = 移除 `name-zh` 键,文件再无数据时连文件一起删除;格式错误和写入失败均保留输入并提示

## 0.1.0 — 2026-08-17

**中文项目名显示(name-zh)✅ 已上线**

- 图标视图在文件夹英文名下方显示 `.project.yaml` 顶层 `name-zh` 的中文名
- 磁盘名/路径/F2 改名不受影响;改中文名直接编辑 yaml
- 右键空白处菜单全局开关(动作式标签:隐藏/显示中文项目名),切换即时生效
- captions 自动配置并备份恢复;状态存 `~/.config/nautilus-project-zh/state`
- 在 `2.nautilus-ex` 项目完成(原提交 `d0a969f`),本仓库引入并建立文档体系

**归档功能探索(未上线)**

- 排序置底:验证不可行(纯插件,gvfs 只存 `metadata::` 命名空间)——详见 `research.md` 死路清单
- emblem 角标:实现后用户决定撤销——详见 `pitfalls.md`(index.theme、双菜单等坑)
- 字段约定:`archived: true`(保留备用)

## 0.2.0 — 计划中

- **决策(2026-08-18)**:fork 基底 = **`gnome-50` 稳定分支**(`main` 开发线要求未发布的 glib ≥ 2.89,在稳定系统上无法构建);本地 `main` 已重置为 gnome-50 并保留全部文档提交(GitHub fork 的 main 未动)
- **初始构建成功(2026-08-18)**:`meson setup build -Ddocs=false && ninja`,404 目标全过,产物 `build/src/nautilus`(约 16 核 2 分钟内;1 条无害警告,上游 GI 绑定自带)

- **决策(2026-08-17)**:显示名覆盖钩子**已否决**——底部 caption 方案更优(理由:心智一致性/零 fork 成本/信息更全/无边界怪癖,详见 `research.md` 第 1 节)。fork 唯一动机 = **分组视图**
- **分组机制已实现(2026-08-19)**,设计见 `design/grouped-view.md`:
  - C 钩子:新增 `nautilus-grouped-view.c`(分组键读取 + 3 个 sorter 工厂)、`nautilus_file_get_extension_attribute` 访问器(绕开 `group` 属性名与 POSIX 组名的内建冲突)、`nautilus_view_model_sort` 补发 `sections-changed`(修复 GtkSortListModel 无位移重排静默)
  - 图标视图:单元格顶部组头横条(仅组内第一项,同组其余项预留等高空位对齐);列表视图:原生 `gtk_column_view_set_header_factory` 组头
  - 未分组条目排最前、不渲染任何"未分组"组头;组间按分组键 strcmp 升序,`reversed` 只影响组内
  - 列表视图:原生 header factory 整行组头;图标视图:**每个分组项图标中央显示分组名徽章**(GtkGridView 无 section 感知、无法让分组另起一行——源码级确认;徽章半透明黑底白字+描边,按文件夹图标形状居中,`can-target: false` 点击穿透)
  - Python 测试驱动:`archived: true`(严格布尔)→ `group` 扩展属性 `已归档`;**分组与 name-zh 开关解耦**(开关只控制中文名)
  - 构建验证通过(2026-08-19);扩展安装 `~/.local/share/nautilus-python/extensions/` 实测加载正常
- **列表视图中文项目名(2026-08-19)**:`nautilus-name-cell` 名称单元格在英文 `display-name` 后追加 `name-zh` 中文名 label,样式沿用网格视图 caption 的 `caption + dim-label`(同一颜色);`file-changed`/bind 时随 `update_labels` 刷新,无中文名时隐藏
- 扩展重组(后续):改名 `nautilus-meta.py`(菜单 ID、配置目录同步),纳入 `plus/extensions/python/`
