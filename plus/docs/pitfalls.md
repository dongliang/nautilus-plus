# 踩坑记录

按严重度排列,全部为实际踩过或源码级验证的坑。

## 1. GFileEnumerator 不是上下文管理器

- **现象**:`with children:` 抛 `TypeError: object does not support the context manager protocol`
- **原因**:pygobject 的 `Gio.FileEnumerator` 只有 `__iter__`/`__next__`,没有 `__enter__`/`__exit__`
- **处理**:直接 `for info in children:` 迭代,`finally` 里 `children.close(None)`(包 GLib.Error)

## 2. 菜单标签冻结(nautilus 只构建一次扩展菜单)

- **现象**:切换开关后,右键菜单标签不更新,一直显示旧状态
- **原因**:nautilus 的扩展菜单模型只在视图加载时构建一次(`nautilus-files-view.c:8173`),之后复用;`popup-menu-changed` 信号是死代码(全树无人发出);`items-updated` 信号同样无人监听
- **处理**:切换后对当前文件夹重加一次扩展属性 → `nautilus_file_changed` → 视图调度菜单重建,标签约 0.5s 内翻转

## 3. gvfs 只存储 metadata:: 命名空间(排序置底死路)

- **现象**:`Gio.File.set_attribute_int32('standard::sort-order', …)` 报 `not supported`
- **原因**:本地文件的未知命名空间属性委托给 gvfs,但 `g_daemon_vfs_local_file_set_attributes`(`gdaemonvfs.c:1202`)只处理 `metadata` 命名空间;且查询合并时强制给存储键加 `metadata::` 前缀(`gdaemonvfs.c:1054`)
- **结论**:扩展路径无法影响 nautilus 的 `sort_order`(`nautilus-file.c:2743` 只读 `standard::sort-order`)。fork 内改 C 代码除外

## 4. index.theme 缺 Directories 键 → 图标找不到

- **现象**:GTK 警告 `Theme file for hicolor has no directories`,自定义 emblem 图标不显示
- **原因**:GTK 认为没有 Directories 声明的主题无目录,不扫描
- **处理**:写 `index.theme` 时必须包含 `Directories=` 及对应 `[目录]` 段;存在旧 `icon-theme.cache` 时需 `gtk-update-icon-cache -f`(异步 spawn)

## 5. 旧安装文件残留 → 双菜单

- **现象**:插件改名/换目录后,右键菜单出现两份相同菜单项
- **原因**:nautilus-python 同时加载用户目录和系统目录下所有扩展文件,旧文件名残留即重复加载
- **处理**:改名/迁移时删除旧路径的安装文件(`~/.local/share/nautilus-python/extensions/`)

## 6. 扩展属性没有 remove

- **现象**:开关关闭后,已显示的 caption/标记不消失
- **原因**:`add_string_attribute` 只有 add;`invalidate_extension_info` 会清空扩展数据再重跑 provider,但仅在被触发时
- **处理**:置空串 `add_string_attribute(attr, '')` 清显示;用进程内集合(`_shown`)追踪"曾设置过"的文件夹,避免每次列目录重复写入

## 7. YAML 1.1 的 yes/on 陷阱

- **现象**:`archived: yes` 被 PyYAML 解析为 `True`,与 `true` 无法区分
- **原因**:`yaml.safe_load` 是 YAML 1.1 语义
- **处理**:文档注明;布尔字段取值只承诺 `true`/`false`

## 8. `__pycache__` 残留

- **现象**:`python3 -m py_compile` 在源码目录生成 `__pycache__/`
- **处理**:.gitignore 忽略;安装目录出现时手动清理

## 9. 无热重载

- **现象**:修改插件后不生效
- **处理**:`nautilus -q` 重启(加载错误在 stderr,启动时重定向到日志可捕获);fork 用 `nautilus-plus -q`

## 10. Arch 把开发工具拆进子包(2026 实测)

- **现象**:meson setup 报 `Program 'xxx' not found` 或 `tool variable contains erroneous value: '/usr/bin/xxx'`——后者典型的例子:`.pc` 文件声明了工具路径,但文件不存在
- **原因**:Arch 把 glib 系 Python 开发工具拆出主包:
  - `gdbus-codegen` → **`glib2-devel`**(glib2 的 optdepends)
  - `g-ir-scanner` → **`gobject-introspection`**(用户只装了 `gobject-introspection-runtime`)
  - 另需:`blueprint-compiler`(.blp 蓝图)、`itstool`、`libselinux`(构建头文件)、`meson`
- **处理**:构建前一次性装齐:`sudo pacman -S --needed meson glib2-devel gobject-introspection blueprint-compiler itstool libselinux`

## 11. fork 用 main 分支构建失败

- **现象**:`Dependency 'gio-2.0' ... found 2.88.3 but need: '>= 2.89.0'`
- **原因**:上游 `main` 是开发线,依赖未发布版本的 glib;稳定系统只有 2.88.x
- **处理**:fork 基底用稳定分支 `gnome-50`(见 `research.md` 架构决策)

## 12. 直接运行构建产物时 prefix 必须为 /usr

- **现象**:跑 `build/src/nautilus` 时菜单全英文、扩展不加载,stderr 出现 `'file:///usr/local/share/nautilus/ontology' is not a ontology location`
- **原因**:meson 默认 prefix 是 `/usr/local`,而 Arch 系统在 `/usr`——翻译目录、扩展目录(`/usr/lib/nautilus/extensions-4`)、ontology 全部指向不存在的 `/usr/local/...`
- **处理**:setup 时指定 `--prefix=/usr`:`meson setup build --prefix=/usr -Ddocs=false`;已配置的用 `meson setup --reconfigure build --prefix=/usr` 重配后重编

## 13. 自定义 desktop/metainfo 用 configure_file 后,validate 测试的 depends 报错

- **现象**:`meson setup` 报 `test keyword argument 'depends' was of type array[File] but should have been array[BuildTarget | ...]`
- **原因**:上游 validate 测试 `depends: [desktop]`,但 `i18n.merge_file` 返回 CustomTarget 而 `configure_file` 返回 File,File 不能作 depends
- **处理**:configure_file 分支的 validate 测试直接传 `join_paths(meson.current_build_dir(), 文件名)` 字符串路径、省略 depends(见 `data/meson.build` Plus 分支)

## 14. appstreamcli 不接受 `<description xml:lang="...">`

- **现象**:`validate-appdata` 报 `metainfo-localized-description-tag` 错误
- **原因**:AppStream 的 description 只能有一份,本地化走翻译系统,不允许按语言给整段 description 换内容
- **处理**:`<name>`/`<summary>` 可以带 `xml:lang`,description 不行——中文说明并入同一个 description 的 `<p>` 里

## 15. fork 专属键放进发行版包拥有的 schema 文件 → 系统升级后闪退

- **现象**:全量 `pacman -Syu` 后 `nautilus-plus` 一开窗口就退出,stderr 只有一行:
  `GLib-GIO-ERROR **: Settings schema 'org.gnome.nautilus.preferences' does not contain a key named 'hide-archived'`
- **原因**:fork 把 `hide-archived` 加进了 `data/org.gnome.nautilus.gschema.xml`,而它安装到的
  `/usr/share/glib-2.0/schemas/org.gnome.nautilus.gschema.xml` **由发行版的 `nautilus` 包拥有**。
  包一升级,pacman 把文件换回上游版本 → fork 的键消失。而 `g_settings_get_boolean()` 读不存在的键是
  `g_error()`(不是可捕获的异常/返回错误),进程直接 abort
- **定位手法**:`pacman -Qo <schema 路径>` 看归属;`grep -c <键名> <已安装 schema>` 对比源码
- **处理**:
  1. 键迁到 fork 自有文件 `plus/gschema/org.gnome.NautilusPlus.gschema.xml`(schema id 也独立),
     上游 schema 恢复原样 → 升级不再影响(见 `design/hide-archived.md`)
  2. C/Python 两侧都先 `lookup()` + `has_key()` 再取设置对象,缺失时降级("显示归档")而非 abort。
     **注意 Python 侧 `Gio.Settings.new()` 同样会 abort,`try/except` 抓不住**——必须先 lookup,
     再用 `Settings.new_full(schema, None, None)`
- **通用教训**:fork 的任何键/文件都不要落在发行版包拥有的路径上;读取第三方可能缺失的键时先做存在性检查
