# 功能设计:隐藏归档汇总卡片

状态:**已实现**(C 层独立尾部条目,2026-08-26)

## 背景

「隐藏归档」(hide-archived.md)把已归档文件夹从视图里完全过滤掉后,用户再也看不到"这里还有 N 个已归档项目"。本功能在视图**末尾**显示一张汇总卡片:分组名 + 数量 + 部分条目名称,点击后**会话级临时显示**被隐藏的条目。

## 需求决策(用户已确认)

1. **显示条件**:仅当「隐藏归档」开启且当前目录存在归档条目时;其余情况卡片不出现
2. **内容**:分组名(「已归档」)+ 数量 + 部分被隐藏条目的名称(描述 `desc` 优先,没有则用英文显示名);卡片有余位时最多列 3 个,超出显示「等 N 个」
3. **尺寸**:网格模式占一个完整单元格;列表模式占一个条目行
4. **位置**:始终在末尾(排序/过滤链之后)
5. **点击行为**:临时显示全部被隐藏条目(不清除持久化设置);**导航到其他目录时自动恢复隐藏**
6. **实现约束**:用独立卡片对象,不伪造 `NautilusFile`(伪造文件会污染菜单/属性/选中逻辑)

## 架构

```
GListStore<NautilusViewItem> ── 1 个 auxiliary item
(hidden_group_card_store)    │  └─ NautilusHiddenGroupCard(GObject) 挂到
                             │     NautilusViewItem.auxiliary(无 file)
                             ▼
NautilusViewModel.model_list = GListStore<GListModel>
  [0] sort_model(常规文件行) ─────┐
  [1] tail_tree_model(卡片) ──────┤
                                 ▼
              GtkFlattenListModel(4.22 实现 GtkSectionModel)
                    │
                    └─ GtkMultiSelection / GtkSingleSelection
```

- **拼接点**:`GtkFlattenListModel` 把「常规排序结果」与「尾部模型」拼成单条连续流,天然支持 section(卡片自成最后一节,列表视图出现独立组头——用 `bind_group_header` 对 auxiliary item 隐藏 label,卡片自身即组头)
- **不进文件管线**:尾部模型不经过 `root_filter_model`/`tree_model`/`sort_model`,文件排序、过滤、子目录展开全部不受影响
- **首次加载的 ready barrier**:隐藏归档开启时,`files-view` 在安装文件 monitor 前请求子项 `EXTENSION_INFO` 并等待完整文件列表;`nautilus-directory-async.c:request_is_satisfied()` 现在真正检查扩展 provider 是否完成。因此首次进入目录时,归档状态和分组主键已经参与初始排序,不会先按未知分组显示再整批重排;隐藏关闭时仍走原有快速增量加载路径
- **归档组固定置底、组内规则不变**:共享 `compare_group_keys()` 把 `ARCHIVED_GROUP_KEY` 作为最后分组,普通组之间仍按原 `strcmp()`;GtkMultiSorter 后续继续使用原来的名称/日期/大小、directories-first 或网格排序器,所以只是分组位置改变,组内排序不变
- **选中隔离**:view-model 的 `GtkSelectionModel` 转发器对尾部位置返回 FALSE(不可选/不可选中),`set_selection`/`get_selection_in_range` 主动剔除尾部位置;列表行 `gtk_column_view_row_set_selectable(FALSE)`
- **卡片即按钮**:`NautilusHiddenGroupCard` 是纯 GObject(分组名/数量/明细属性 + `activate` 信号),`create_widget()` 按模式生成 `GtkButton`(CSS 类 `hidden-group-card`,网格竖排/列表横排),视图 bind 时装入预建的 `GtkStack`「card」页;`notify` 自动刷新 label

## 数据流(nautilus-files-view.c)

```
files_view_end_file_changes()
  └─ update_hidden_group_card():
       filter 未启用 / 统计为 0 → remove_all(卡片消失)
       否则 → 遍历 dup_unfiltered_root_items()
              (root_filter_model 之下的原始 store,未被归档过滤器碰过)
              统计 group == 已归档 的条目
              desc quark 优先取显示名,「、」拼接,最多 3 个
              set_summary(count, details) → 追加 auxiliary item 到尾部 store
```

- **计数数据源**:`nautilus_view_model_dup_unfiltered_root_items()` 取根 store 原文(过滤前),才能统计"被藏了多少"
- **点击** → `hidden_group_card_activated()`:`nautilus_archived_filter_set_temporarily_disabled(TRUE)` —— 过滤器 `enabled = setting_enabled && !temporarily_disabled`,gsettings 里的持久化设置不动;条目即时回归,卡片消失(过滤器已禁用,统计为 0)
- **全局开关变更** → `hide_archived_changed()` 先清除 `temporarily_disabled`,再按新的 gsettings 值更新 `enabled`;因此卡片临时显示后,无论切换「显示归档」还是「隐藏归档」,当前文件夹都会立即跟随全局状态,不会残留旧的临时显示覆盖。Python 侧仍刷新当前文件夹扩展属性并触发菜单标签更新,不做昂贵的目录重载
- **导航重置**:`set_location()` 里 `set_temporarily_disabled(FALSE)` + 清空尾部 store,回到正常隐藏状态——临时显示只活到下一次导航
- **多视图共享**:view model 每视图一个,卡片 store 在 files-view 里(每个 slot/view 一份),互不干扰

## 关键文件

- `src/nautilus-hidden-group-card.{c,h}`(新)——卡片对象与两视图共用的 widget 构建
- `src/nautilus-view-item.{c,h}`——`auxiliary` 字段:`nautilus_view_item_new_auxiliary()` / `get_auxiliary()` / `is_auxiliary()`
- `src/nautilus-view-cell.c`——`PROP_ITEM` 守卫:无 file 的 auxiliary item 不绑进文件单元格
- `src/nautilus-view-model.{c,h}`——flatten 拼接链、`set_tail_model()`、`dup_unfiltered_root_items()`、选中转发器
- `src/nautilus-grid-view.c` / `src/nautilus-list-view.c`——bind 时切到「card」页;列表其余列 `bind_non_name_cell` 隐藏
- `src/nautilus-archived-filter.{c,h}`——`temporarily_disabled` 覆盖位
- `src/resources/style.css`——`.hidden-group-card`(虚线边框、圆角、hover/active)

## 已知边界

- 排序/搜索模式:卡片同样出现在尾部(搜索即过滤,`end_file_changes` 也会刷);搜索中点击卡片临时显示后,条目仍需匹配查询才可见
- 非分组视图(未启用分组):`nautilus_grouped_view_get_group_string` 对未分组条目返回非「已归档」值,统计恒为 0 → 卡片不出现,与过滤行为一致
- FileChooser(mode != BROWSE)也走同一 files-view:过滤器生效处卡片同现,接受
- 卡片不可选中、不进剪贴板/拖拽;菜单对 auxiliary item 无动作

## 坑:过滤匹配先于扩展属性就绪

扩展属性由 nautilus-python 的 info provider 以 idle 异步提供,而增量新增/属性失效更新可能在属性完成前进入视图模型——**匹配发生在前、属性就绪在后**。如果只依赖过滤器在属性到达后重评估,归档条目会先放行、再移除,并可能触发整批重排。

修复(三件套):

1. **首次加载 ready barrier**:`load_directory()` 在隐藏归档开启时把 `NAUTILUS_FILE_ATTRIBUTE_EXTENSION_INFO` 加入目录 ready 请求并设置 `wait_for_all_files=TRUE`;`request_is_satisfied()` 增加 `REQUEST_EXTENSION_INFO` 分支,用现有 provider pending 状态判断。首次安装 monitor/把条目交给视图前,扩展属性和文件列表已经完成,因此首次排序/过滤就是最终状态;隐藏关闭时不增加等待,保留原有速度。
2. **就绪前保守隐藏**(动态增量避免"显示一瞬再隐藏"):`NautilusArchivedFilter::match` 对「目录且扩展属性仍在检索中(`nautilus_file_is_extension_info_pending`)」的条目直接返回 FALSE——新增归档文件夹不会闪现,非归档文件夹在属性就绪后的重评估中正常回归;文件永不归档,直接放行不受影响。扩展未安装时 provider 列表为空、`pending` 恒为 FALSE,按原逻辑放行(安全退化)。
3. **就绪后重评估并同步 UI**:`files_view_file_changed` 与 `files_view_end_file_changes` 都调用 `schedule_archived_refilter()`,以 idle 合并批量文件变化,在空闲时对 archived filter 发一次 `GTK_FILTER_CHANGE_DIFFERENT` 全量重评估、刷新卡片、空状态页和工具栏(dispose 时 `g_clear_handle_id` 清理)。此兜底覆盖动态新增、外部修改 `.folder.yaml` 和 provider 重新失效。
