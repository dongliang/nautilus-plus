# 功能设计:fork 独立身份(nautilus-plus)

状态:**已实现**(v0.3.0,`-Dprofile=Plus` 构建)

## 需求

- 软件以 **nautilus-plus** 的名字存在,与本地(系统)nautilus **不冲突**
- 显示的中文名为 **文件管理器增强版**(zh_CN 环境)
- 本地 nautilus 仍是系统默认文件管理器,不被 fork 抢占

## 方案:Plus profile(构建期身份)

fork 不修改上游默认行为,新增 meson `profile=Plus` 分支(复用上游已有的 profile 机制,上游 `Devel` profile 就是为并行安装设计的):

```
meson setup build --prefix=/usr -Dprofile=Plus -Ddocs=false
```

| 身份项 | 系统 nautilus | nautilus-plus(fork) |
|---|---|---|
| 二进制 | `/usr/bin/nautilus` | `/usr/bin/nautilus-plus` |
| Application ID | `org.gnome.Nautilus` | `org.gnome.NautilusPlus` |
| 桌面文件 | `org.gnome.Nautilus.desktop` | `org.gnome.NautilusPlus.desktop` |
| 图标 | `org.gnome.Nautilus*.svg` | `org.gnome.NautilusPlus*.svg` |
| D-Bus service | `org.gnome.Nautilus.service` | `org.gnome.NautilusPlus.service` |
| 搜索提供者 | `org.gnome.Nautilus.search-provider.ini` | `org.gnome.NautilusPlus.search-provider.ini` |
| 显示名(zh_CN) | 文件 | 文件管理器增强版 |

## 无冲突点(逐个验证)

1. **GApplication 总线名**:`org.gnome.Nautilus` vs `org.gnome.NautilusPlus`,互不抢占(`nautilus-application.c` 用 `APPLICATION_ID` 构造,meson 里 `application_id = 'org.gnome.Nautilus' + 后缀`)
2. **FileManager1(`org.freedesktop.FileManager1`)**:系统默认文件管理器的唯一入口。Plus 构建**不注册、不安装 service 文件**——fork 绝不抢"打开文件夹"请求;系统 nautilus 的默认角色不受影响。实现:`nautilus-application.c` 中 `PROFILE == "Plus"` 时跳过 `nautilus_freedesktop_dbus_new/register`,两处 `set_open_locations` 调用点加 NULL 守卫;`data/meson.build` 不安装 `org.freedesktop.FileManager1.service`
3. **预览器**:`"org.gnome.NautilusPreviewer" PROFILE`(`nautilus-previewer.c`)→ `org.gnome.NautilusPreviewerPlus`,独立名字,不抢系统预览器
4. **对象路径**:`"/org/gnome/Nautilus" PROFILE "/SearchProvider"`、`"/FileOperations2"` → 均带 Plus 后缀,与系统实例无交集
5. **搜索提供者 ini**:`BusName=@appid@`、`ObjectPath=/org/gnome/NautilusPlus/SearchProvider`,与 C 代码一致;shell 里 fork 是独立条目
6. **共享(刻意不隔离)**:
   - GSettings schema `org.gnome.nautilus`(文件内容与系统相同;共享设置=体验一致,属协作非冲突)
   - `libnautilus-extension` 同 soname(系统 Python 扩展依赖它)
   - 翻译 `nautilus.mo`、`/usr/lib/nautilus/extensions-4/`、ontology(内容与系统完全相同,覆盖无害)

## 显示名「文件管理器增强版」

显示名来自两处,均由 **fork 自有的桌面/元数据文件**(`plus/desktop/`)硬编码提供,不走上游 po 翻译(否则 zh_CN 会翻成「文件」):

- 桌面文件 `plus/desktop/org.gnome.NautilusPlus.desktop.in`:`Name=nautilus-plus`、`Name[zh_CN]=文件管理器增强版`、`Exec=nautilus-plus --new-window %U`
- metainfo `plus/desktop/org.gnome.NautilusPlus.metainfo.xml.in`:同名;关于对话框(`adw_about_dialog_new_from_appdata` 读 `/org/gnome/nautilus/appdata` 资源,资源内容即本 metainfo)显示「文件管理器增强版」

`data/meson.build` 在 Plus 分支用 `configure_file` 直接生成这两个文件(输出名跟随 `@appid@`,gresource 依赖不变);非 Plus 分支保持上游 i18n.merge_file 路径不变。

## C 改动清单(全部受 profile 门控,上游默认行为不变)

- `src/nautilus-application.c:221`:`devel` CSS class 仅 `PROFILE == "Devel"` 时添加(原来任何非空 profile 都会加)
- `src/nautilus-application.c:1038` 附近:Plus 时跳过 freedesktop dbus 注册;`update_dbus_opened_locations` 里两处调用加 `if (self->fdb_manager != NULL)` 守卫

## 图标

复用上游 `org.gnome.Nautilus.svg` 内容,放 `plus/icons/org.gnome.NautilusPlus.svg`(构建期按 `@appid@` 重命名安装)。symbolic 图标直接复用上游文件重命名。

## 安装与回滚

```bash
# 构建+安装
meson setup build --prefix=/usr -Dprofile=Plus -Ddocs=false
ninja -C build
sudo ninja -C build install   # 覆盖安装;pacman 更新系统 nautilus 时会还原共享文件,重装一次即可

# 启动
nautilus-plus
```

回滚:删除 `/usr/bin/nautilus-plus`、`org.gnome.NautilusPlus.*`(桌面/图标/metainfo/service/搜索提供者),共享文件不动。系统 nautilus 全程不受影响。