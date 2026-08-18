# plus/ — fork 专属内容

本目录存放 nautilus-plus 相对上游 nautilus 的全部**自有内容**,与上游代码隔离。

**为什么独立成目录**:上游 nautilus 已有 `docs/`(man 页 + gtk-doc 参考)和 `extensions/`(meson 管理的 C 扩展)——把我们的文档和 Python 扩展放进去会污染上游结构、增加合并摩擦。`plus/` 是独立命名空间,上游合并永不触碰。

## 结构

```
plus/
├── README.md        # 本文件:目录导航
├── docs/            # 项目文档体系(可扩展)
│   ├── requirements.md   # 原始需求(短、笼统)
│   ├── design/           # 功能设计(按功能一个文件)
│   │   └── name-zh.md
│   ├── research.md       # 技术调研(已验证的机制/死路/fork 钩子蓝图)
│   ├── pitfalls.md       # 踩坑记录
│   └── CHANGELOG.md      # 版本日志
└── extensions/
    └── python/           # Python 扩展(业务层,nautilus-python 插件)
        └── project-name-zh/
```

## 开发分工

- **C 层**(本仓库主树):新能力钩子(显示名覆盖、分组机制等)——能力放 C,规则放 Python
- **Python 层**(`extensions/python/`):业务逻辑(.project.yaml 解析、开关、菜单)——修改快速迭代,装到 `~/.local/share/nautilus-python/extensions/` 即可

详见 `docs/research.md` 的架构决策章节。
