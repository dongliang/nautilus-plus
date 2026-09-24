# 功能设计:文件注释(file-desc)

状态:**已实现**(Python 扩展,2026-09-25)

## 背景

`.folder.yaml` 原本只能描述文件夹自身(`desc`)。实际使用中经常需要给**文件夹内的某个文件**加一句说明——「这份是会议记录」「这是最终版」——而不改文件名、不造额外的说明文件。

## 需求决策(用户已确认)

1. **注释同样显示**:复用文件夹描述那条显示通道(`desc` 扩展属性 → 图标视图副标题 + 列表视图描述行),因此 **C 层零改动**
2. **只对文件生效**:子文件夹仍由它自己的 `.folder.yaml` 描述。避免同一显示位有两个来源
3. **顶层键名 `file-desc`**:值为「文件名 → 注释」的映射

## 数据格式

```yaml
desc: 我的项目          # 文件夹自身的描述
archived: false
file-desc:              # 文件夹内文件的注释
  notes.txt: 会议记录
  report.pdf: 季度报告
```

- 键为**同级文件名**(basename),不含路径
- 读取侧接受块式(默认)与流式(`{a.txt: x}`)两种写法;写入侧统一产出块式
- 空值或纯空白的注释视为无注释,不显示

## 实现

### 显示(nautilus-meta.py)

`_apply()` 分两条路径:

- **文件夹** → 读自身 `.folder.yaml` 的 `desc`,并处理 `archived` 分组
- **文件** → 读**父目录** `.folder.yaml` 的 `file-desc[basename]`,有值且开关打开则 `add_string_attribute('desc', 注释)`

`_yaml_cache` 因此按目录缓存整份解析结果(desc / archived / file_descs),以 mtime 失效——同目录下 N 个文件只解析一次。`_refresh_folder()` 本来就对每个子项调用 `_apply()`,注释随刷新自动生效。

受同一个「隐藏/显示描述」开关控制:关掉后文件夹描述与文件注释一起消失(`_shown` 统一追踪"曾显示过的路径",路径唯一,文件夹与文件可共用一个集合)。

### 编辑(右键菜单)

单选一个本地文件 → 「修改注释」;单选一个本地文件夹仍是「修改描述」+「归档/取消归档」;多选仍只有归档项。

`_open_editor()` 是两种编辑共用的 GTK4 单行窗口(标题、字段标签、初值、保存回调参数化),按 URI 去重、Escape 关闭、写入失败时保留窗口与输入。保存路径:

- 非空 → `_write_file_desc(父目录, 文件名, 值)`
- 空 → `_remove_file_desc_in_folder(父目录, 文件名)`

### YAML 局部更新

现有 `_replace_yaml_key()` / `_remove_yaml_key()` 只处理顶层键。本次把它们重构为「面向任意映射节点」的 `_put_in_mapping()` / `_remove_from_mapping()`,顶层调用保持原语义(现有测试即回归保障),嵌套调用则以 `file-desc` 的值节点为目标:

- 插入位置取该映射的 `end_mark`(实测 PyYAML 的块映射节点跨度**包含末尾换行**);缩进取自首个条目
- 键名转义不手写:`yaml.safe_dump({名: 值}, default_flow_style=True).strip()` 去掉花括号后的内文,块式与流式下都是合法的 `<键>: <值>`
- `file-desc` 不存在则新建;移除最后一个条目后连键一起删;文件再无数据则连同 `.folder.yaml` 一起删(沿用既有语义)
- `file-desc` 存在但不是映射时**报错拒绝写入**,不覆盖用户数据

## 已知限制

- **注释以文件名为键**:文件重命名或移出目录后,注释留在原键上失效(不报错、不自动跟随)。v1 接受;可在对话框里重新编辑,或手工删除该条目
- 同一目录内文件名唯一,键不会冲突
- 每个文件刷新时会对父目录的 `.folder.yaml` 做一次 mtime 检查(缓存命中即一次 stat),量级与现有文件夹路径相同

## 关键文件

- `plus/extensions/python/nautilus-meta/nautilus-meta.py` —— `_yaml_data()` / `_yaml_file_descs()`、`_set_file_desc()` / `_remove_file_desc()`、`_write_file_desc()` / `_remove_file_desc_in_folder()`、`_put_in_mapping()` / `_remove_from_mapping()`、`_apply()`、`get_file_items()`、`_open_editor()`
- `plus/extensions/python/nautilus-meta/test_nautilus_meta.py` —— `FileDescYamlTests`、`ApplyAnnotationTests`

## 验证

- Python 单测:嵌套写入(新建键 / 追加 / 替换并留注释 / 流式 / 特殊文件名加引号 / 重复键与非法结构报错)、嵌套移除(留下其余、空键连删、空文件连删、不存在则不动)、`_apply` 的文件分支(设值 / 无注释不设 / 空白不设 / 开关关闭不设 / 移除后清空)
- 手工验收:`plus/dev-demo` 下给 `notes.txt` 加注释 → 图标视图副标题与列表视图描述行均显示;清空后消失;关闭「显示描述」开关后一并隐藏;手改 `.folder.yaml` 加注释后刷新亦生效
