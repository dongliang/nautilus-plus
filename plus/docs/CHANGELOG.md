# 版本日志

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

- **决策(2026-08-17)**:显示名覆盖钩子**已否决**——底部 caption 方案更优(理由:心智一致性/零 fork 成本/信息更全/无边界怪癖,详见 `research.md` 第 1 节)。fork 唯一动机 = **分组视图**
- 扩展重组:改名 `nautilus-meta.py`(菜单 ID、配置目录同步),纳入 `plus/extensions/python/`
- 分组机制按 `research.md` 第 2 节蓝图评估(唯一剩余的 fork 钩子)
