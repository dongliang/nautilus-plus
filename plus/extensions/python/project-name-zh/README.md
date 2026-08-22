# nautilus 中文项目名 (project-name-zh)

nautilus 插件:如果文件夹里有 `.project.yaml` 且包含顶层 `name-zh` 字段,在图标视图的文件夹名下方显示中文名。磁盘上的英文文件夹名、路径、F2 改名均不受影响;改中文名直接编辑 `.project.yaml` 即可。

```
  📁                 📁
proj1              blog
我的第一个项目      博客
```

## 安装

```bash
mkdir -p ~/.local/share/nautilus-python/extensions
cp project-name-zh.py ~/.local/share/nautilus-python/extensions/
nautilus -q        # 重启 nautilus
```

依赖:nautilus-python、python-yaml(Arch: `sudo pacman -S nautilus-python python-yaml`)。

## 用法

- 首次加载插件会自动把图标视图 captions 设为 `['name-zh', ...]`(默认开关为开),中文名立即生效
- 右键单个本地文件夹 → 「修改中文名」:打开单行输入框,已有 `name-zh` 会预填;确认后更新或创建文件夹内 `.project.yaml`,不改变磁盘文件夹名
- 清空输入后确认 = 删除中文名:只移除 `name-zh` 键(其他字段、注释保留);文件里再无任何数据时整个 `.project.yaml` 一并删除
- 更新已有 `.project.yaml` 时保留其他字段、注释和原有结构;非法 YAML 或写入失败会提示并保留窗口中的输入
- 右键文件夹**空白处** → 「隐藏中文项目名」/「显示中文项目名」:全局开关,点击后名字立即消失/出现,菜单标签也在片刻后翻转(nautilus 无菜单重建 API,靠当前文件夹变化事件触发,约 0.5 秒内生效)
- 关闭时自动恢复你原来的 captions 设置(原值备份在 `~/.config/nautilus-project-zh/captions-backup.json`,恢复后删除)
- 开关状态存在 `~/.config/nautilus-project-zh/state`(`on`/`off`,默认 `on`)
- 删除 `.project.yaml` 或移除其中 `name-zh` 字段后,刷新文件夹即可清除已显示的中文名

## .project.yaml 格式

```yaml
name: proj1          # 任意字段,不影响
name-zh: 我的第一个项目
```

只认顶层 `name-zh` 键;缺失、非字符串或 YAML 解析失败时该文件夹不显示中文名。

## 注意事项

- 图标缩放最小档时 nautilus 只显示 1 行文字(英文名),中文名在放大一档后出现——这是 nautilus 自身行为
- 列表视图不受影响(中文名只在图标视图显示)
- nautilus 插件不会出现在 GNOME「扩展」应用里;加载错误会出现在 `journalctl --user` 日志中
