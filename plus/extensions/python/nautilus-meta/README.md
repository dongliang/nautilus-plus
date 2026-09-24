# nautilus 描述 (nautilus-meta)

nautilus 插件:如果文件夹里有 `.folder.yaml` 且包含顶层 `desc` 字段,在图标视图的文件夹名下方显示描述。磁盘上的英文文件夹名、路径、F2 改名均不受影响;改描述直接编辑 `.folder.yaml` 即可。

```
  📁                 📁
proj1              blog
我的第一个项目      博客
```

## 安装

```bash
mkdir -p ~/.local/share/nautilus-python/extensions
cp nautilus-meta.py ~/.local/share/nautilus-python/extensions/
nautilus -q        # 重启 nautilus
```

依赖:nautilus-python、python-yaml(Arch: `pkexec pacman -S nautilus-python python-yaml`)。

## 用法

- 首次加载插件会自动把图标视图 captions 设为 `['desc', ...]`(默认开关为开),描述立即生效
- 右键单个本地文件夹 → 「修改描述」:打开单行输入框,已有 `desc` 会预填;确认后更新或创建文件夹内 `.folder.yaml`,不改变磁盘文件夹名
- 右键单个文件 → 「修改注释」:把注释写进**所属文件夹** `.folder.yaml` 的 `file-desc`(文件名 → 注释),显示位置与文件夹描述相同
- 清空输入后确认 = 删除描述:只移除 `desc` 键(其他字段、注释保留);文件里再无任何数据时整个 `.folder.yaml` 一并删除
- 右键文件夹(支持多选)→ 「归档」/「取消归档」:写入或移除 `archived: true`;归档的文件夹在分组视图中形成「已归档」组(图标徽章/列表组头)。全部已归档时标签为「取消归档」;混合选择只对未归档的生效。取消归档后文件无数据时一并删除
- 右键空白处 → 「隐藏归档」/「显示归档」(仅 nautilus-plus):隐藏时已归档文件夹从图标视图、列表视图(含分组头)和搜索结果中完全消失,像不存在一样。状态全局即时生效(gsettings fork-only 键),默认显示
- **隐藏汇总卡片**(仅 nautilus-plus,需 fork 的 C 层):隐藏归档且当前目录有归档条目时,视图末尾出现一张卡片——分组名「已归档」+ 数量 + 至多 3 条名称(描述优先);点击后临时显示被隐藏的条目(不改变「隐藏归档」设置),导航到其他目录自动恢复隐藏。卡片占网格一格/列表一行,不可选中
- 更新已有 `.folder.yaml` 时保留其他字段、注释和原有结构;非法 YAML 或写入失败会提示并保留窗口中的输入
- 右键文件夹**空白处** → 「隐藏描述」/「显示描述」:全局开关,点击后名字立即消失/出现,菜单标签也在片刻后翻转(nautilus 无菜单重建 API,靠当前文件夹变化事件触发,约 0.5 秒内生效)
- 关闭时自动恢复你原来的 captions 设置(原值备份在 `~/.config/nautilus-meta/captions-backup.json`,恢复后删除)
- 开关状态存在 `~/.config/nautilus-meta/state`(`on`/`off`,默认 `on`)
- 删除 `.folder.yaml` 或移除其中 `desc` 字段后,刷新文件夹即可清除已显示的描述

## .folder.yaml 格式

```yaml
desc: 我的第一个项目
archived: false
file-desc:            # 文件夹内文件的注释
  notes.txt: 会议记录
```

只认顶层 `desc` 键;缺失、非字符串或 YAML 解析失败时该文件夹不显示描述。

## 注意事项

- 图标缩放最小档时 nautilus 只显示 1 行文字(英文名),描述在放大一档后出现——这是 nautilus 自身行为
- 列表视图不受影响(描述只在图标视图显示)
- nautilus 插件不会出现在 GNOME「扩展」应用里;加载错误会出现在 `journalctl --user` 日志中
