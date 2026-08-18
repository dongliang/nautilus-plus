# 功能设计:中文项目名显示(name-zh)

状态:**已实现**(扩展 `project-name-zh.py`,v0.1.0)

## 背景

nautilus 50 的扩展 API **无法修改文件夹的显示名**(见 `research.md` 死路清单),因此 v0.1.0 采用"第二行 caption"方案:中文名显示在英文文件夹名**下方**的一行灰字里,不替换英文名。磁盘名、路径、F2 改名完全不受影响。

## 机制

- 图标视图的名字标签是独立控件(captions 之上的第一行,绑定 `display-name` 属性)
- captions 是名字下方的额外行,由 gsettings `org.gnome.nautilus.icon-view` 的 `captions` 键驱动
- captions 值可以是**任意属性名**;nautilus 对未知属性名会回落到扩展属性表(`nautilus-file.c` `nautilus_file_get_string_attribute_q` 的末尾查找)
- 因此:插件 `add_string_attribute('name-zh', 中文名)` + captions 配置 `['name-zh']` → 中文名成为图标下第二行

## 架构

```
InfoProvider.update_file_info(每个可见文件)
  └─ 目录? → 读 <dir>/.project.yaml(PyYAML,顶层 name-zh)
       ├─ 有值且开关开 → add_string_attribute('name-zh', 值)
       └─ 曾显示过且现在无值 → add_string_attribute('name-zh', '') 清空

MenuProvider.get_background_items(右键空白处)
  ├─ 菜单项标签 = 当前状态的**动作**(隐藏/显示中文项目名)
  └─ 激活 → 翻转状态文件 → 同步 captions → 刷新当前目录 → 触发菜单重建
```

## 关键组件

| 组件 | 说明 |
|---|---|
| 状态文件 | `~/.config/nautilus-project-zh/state`(`on`/`off`,默认 on,mtime 缓存) |
| captions 同步 | 开关开:`['name-zh']` + 备份原值;关:恢复原值(原子写入) |
| 实时刷新 | 枚举当前目录子项 → `Nautilus.FileInfo.lookup_for_uri` → `invalidate_extension_info()`(nautilus 会清空扩展属性/角标后重跑 provider) |
| 菜单标签翻转 | 对当前文件夹重加一次扩展属性 → `nautilus_file_changed` → 视图调度菜单重建(约 0.5s) |
| yaml 缓存 | `{path: (mtime, name)}`,上限 1024,解析失败缓存 None |

## 已知边界

- 图标最小缩放档只显示名字一行,captions 隐藏(nautilus 自身行为)
- 列表视图不受影响(只作用于图标视图 captions)
- 非 `file:` URI(网络挂载)跳过
