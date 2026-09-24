# 功能设计:右键归档切换(archived toggle)

状态:**已实现**(扩展 `nautilus-meta.py`,2026-08-22)

## 背景

分组视图(见 `grouped-view.md`)以 `archived: true` 为测试驱动,但此前只能手工编辑 `.folder.yaml` 改归档状态。本功能在选中文件的右键菜单提供「归档」/「取消归档」,复用「修改描述」已建立的 YAML 局部更新基础设施。

## 需求决策(用户已确认)

1. **支持多选批量**:选中多个文件夹时仍显示菜单项,批量处理
2. **单项动态标签**:全部已归档 → 「取消归档」;否则 → 「归档」。与全局开关的动作式标签风格一致
3. **无数据则删文件**:取消归档移除 `archived` 键后若文件再无任何数据,连同删除 `.folder.yaml`(与清空描述语义一致)
4. 混合选择:标签「归档」;点击后未归档的变归档,**已归档的保持不动**(幂等跳过)

## 机制

### 基础设施参数化

「修改描述」原有的 `_replace_yaml_name` / `_remove_yaml_name` 泛化为按键名操作:

| 函数 | 职责 |
|---|---|
| `_replace_yaml_key(text, key, scalar)` | 替换/追加顶层键值(compose marks 定位,保留注释/顺序/CRLF/flow) |
| `_remove_yaml_key(text, key)` | 整行摘除条目;flow 式摘条目+相邻逗号;空则返回 '' |
| `_update_yaml_file(folder, update)` | 统一原子写回框架(缺文件新建、'' 删文件、None no-op) |
| `_set_archived(folder, archived)` | 归档 = 写入字面量 `true`;取消 = 摘键删文件;双向幂等 |
| `_remove_key_in_folder(folder, key)` | 描述清除走同一摘键路径 |

### 菜单逻辑

```
get_file_items(files)
  ├─ 过滤出本地文件夹 (file, path) 列表
  ├─ 全部过滤掉 → 无菜单
  ├─ len(files)==1 → 「修改描述」+ 归档切换项
  │   (多选即使过滤后只剩一个也不给「修改描述」——按用户实际选择的数量判断)
  └─ 动态标签:全部 archived is True → 「取消归档」(目标 False)
              否则 → 「归档」(目标 True)

_on_toggle_archived(folders, target)
  ├─ 逐个 _set_archived(幂等:已处目标态的不重写)
  ├─ 成功 → 清 _yaml_cache + _apply + invalidate_extension_info(即时重排分组)
  └─ 失败收集汇总,弹一个 AlertDialog 列出失败文件夹名+原因;成功的照常生效
```

### YAML 语义

- **归档**:缺失 `.folder.yaml` 时创建只含 `archived: true` 的文件;已有文件按 marks 只替换值区域(`archived: false # 注释` → `archived: true # 注释`)
- **取消归档**:整行摘除(含行尾注释);flow 式 `{archived: true, desc: a}` → `{desc: a}`(摘条目+相邻逗号);摘后无数据删除整个文件
- malformed / 非 mapping / 重复键 / 超大文件:**报错不覆盖**,与描述编辑同一防护

## 已知边界

- 多选里混有非本地文件夹(远程)时:远程成员被忽略,仅本地成员参与批量
- 幂等保证重复点击不产生多余 mtime 变化(测试覆盖 mtime 不变)
- 分组刷新依赖既有链路:`add_string_attribute('group', …)` → `nautilus_file_changed` → sections-changed 补发(grouped-view.md)

## 验证

- 纯函数测试 26 项:归档新建/追加保留注释/替换值/取消摘行/空删文件/缺文件 noop/幂等(mtime)/flow 式/malformed 拒绝
- 菜单测试:单选两项、多选仅切换项、全归档显「取消归档」、非文件夹/远程过滤
- 手工验收:`plus/dev-demo` 里 gamma-project(仅 archived)取消归档 → 徽章消失且 yaml 删除;beta-project 归档 → 出现徽章和组头;多选混合批量
