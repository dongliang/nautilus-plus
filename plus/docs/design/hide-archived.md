# 功能设计:右键空白处切换显示/隐藏归档文件夹

状态:**已实现**(C 过滤器 + Python 开关,2026-08-22)

## 背景

归档分组(grouped-view.md)只是"标注",用户要求真正**隐藏**已归档文件夹——像不存在一样:条目消失、列表视图组头完全消失(不是空组头)、搜索结果同样隐藏。

扩展属性只能标注,不能从视图移除条目;移除必须由 fork 的 C 层过滤(`research.md` 分组蓝图已确认视图模型有 `root_filter_model` = GtkFilterListModel)。因此本功能是 **C 能力 + Python 规则**的组合:

```
Python 扩展(规则)                C 钩子(能力)
──────────────────────          ─────────────────────────────
archived: true → group 属性  →   NautilusArchivedFilter(GtkFilter):
                                  group == 已归档 → 拒绝
开关菜单 + 状态持久化             files-view 构造时与 slot filter
                                  组合进 GtkAnyFilter 接入 model
```

## 需求决策(用户已确认)

1. **搜索结果也隐藏**:搜索走同一 view model 过滤链,自动生效
2. **默认显示**:新安装不隐藏,避免用户以为文件丢了;与中文名开关默认开一致
3. **仅 nautilus-plus 显示菜单**:系统 nautilus 无过滤能力,显示了也没效果
4. **全局状态**:所有视图共用,存 gsettings `org.gnome.nautilus.preferences` 的 `hide-archived` 键(fork-only,布尔,默认 false=显示)

## C 层实现

### 新增 `NautilusArchivedFilter`(nautilus-archived-filter.c/h)

仿照现有 `NautilusViewItemFilter`(FileChooser 用)的最小 GtkFilter:

- `match(item)`:取 item 的 file → `nautilus_grouped_view_get_group_string()` → 等于 `已归档` → FALSE(隐藏);其余 TRUE
- `get_strictness()`:启用时 SOME、停用时 ALL;变更时发 `gtk_filter_changed(MORE_STRICT/LESS_STRICT)` 让 GtkFilterListModel 增量重过滤
- `enabled` 属性可写,供上层开关

### 组合接入(nautilus-files-view.c)

view model 的 `filter` 是单槽位,slot 的既有 filter(FileChooser 场景)不能被顶掉:

```
files-view constructed:
  archived_filter = nautilus_archived_filter_new()
  slot_filter_changed_cb():
    slot==NULL → combined = archived_filter
    否则 → GtkAnyFilter[slot filter, archived_filter]
           (GtkAnyFilter 返回 GtkMultiFilter*,需显式转换)
  nautilus_view_model_set_filter(model, combined)
  → slot "notify::filter" 时重建组合并整体重过滤
```

子目录树展开(create_model_func)把 root filter 绑定到每个子目录 filter_model,**树形模式同样过滤**。

### 组头自动消失

组头由 section sorter 从**可见条目**推导(GtkListView header factory / 网格徽章都读条目自身);条目被过滤掉后该组零条目,section 自然不存在——无空组头残留,无需额外处理。

## Python 层实现

### 开关菜单(ProjectNameZhMenu.get_background_items)

在现有「隐藏/显示中文项目名」旁新增一项:

- 标签:`隐藏归档`(当前显示时)/ `显示归档`(当前隐藏时)——动作式动态标签
- 点击翻转状态 → 写 gsettings → C 过滤器收到 changed 信号自动重过滤(无需手动刷新视图)→ 重加当前文件夹属性触发菜单重建(pitfalls #2 同款机制)

### 状态持久化

gsettings `org.gnome.nautilus.preferences` 新增 fork-only 布尔键 `hide-archived`(默认 false)。**这是 Python 开关与 C 过滤器之间的状态通道**:Python `_set_hide_archived()` 写键,C 侧 `NautilusArchivedFilter` init 时读初始值并监听 `changed::hide-archived`——多窗口即时同步、无需进程间通知。系统 nautilus 不读此键,无影响。

> 踩坑记录:该键最初被误加到 `org.gnome.nautilus.list-view` schema(紧邻 `use-tree-view`),
> 导致 C/Python 双双报"没有键"、过滤永不生效。schema 键必须落在消费方读取的那个 id 里;
> 验证方式:`glib-compile-schemas` 干净目录编译后用 C `g_settings_schema_has_key` 断言。

中文名开关仍走 state 文件(第一行 on/off,兼容旧格式);归档隐藏不走 state 文件。

### 菜单仅在 fork 显示

nautilus-python 扩展同时被系统 nautilus 加载,但系统 nautilus 没有 C 过滤器,点了没效果。检测:`_running_as_plus()` 读 `/proc/self/exe`(nautilus-python 进程内嵌 CPython,exe 即宿主二进制),fallback 到 `/proc/self/cmdline` 与 `argv[0]`;basename 为 `nautilus-plus` 才注册归档菜单项。

## 已知边界

- 过滤器读的是 `group` 扩展属性,依赖 Python 扩展已写入;若扩展未装,无 group 属性 → 全部显示(安全退化)
- 开关切换后重过滤由 `gtk_filter_changed` 增量驱动;无位移场景(view-model sort 补发 sections-changed 已处理)
- FileChooser 场景(mode != BROWSE):归档过滤也生效——打开/保存对话框里隐藏归档文件夹语义一致,接受
- 树形展开模式经 create_model_func 的 filter 绑定自动生效

## 验证

- C:构建通过;手工矩阵:图标/列表 × 显示/隐藏 × 含归档/全归档/无归档目录;树形模式;搜索含归档项
- 切换即时生效;组头随条目消失,无空组头
- Python 单测:状态解析(on/off/缺省/旧行兼容)、菜单标签翻转
- 手工验收 dev-demo:gamma-project 隐藏后从两视图+搜索消失,组头不见;切回显示恢复
