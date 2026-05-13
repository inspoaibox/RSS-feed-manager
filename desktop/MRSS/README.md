# MRSS Desktop

MRSS Desktop 是和安卓 MRSS 对齐的电脑本地端。它不需要登录、注册、多用户或独立服务器；电脑本机就是服务端，数据保存在本机 SQLite。

## 当前功能

- 独立 Windows 窗口客户端，启动 `MRSS.exe` 不再打开浏览器页面
- 现代化三栏界面：左侧分类/订阅，中间文章卡片，右侧阅读面板
- 手动添加 RSS/Atom 链接
- 本地抓取、解析、保存文章
- 应用运行期间每分钟检查到期订阅并自动同步
- 启动后可手动刷新全部、分类或单个订阅
- 分类管理，订阅管理
- 左侧分类/订阅导航，右键分类或订阅可重命名、停用、删除等
- 搜索、未读、收藏、排序、日期过滤
- 阅读文章、自动标记已读、重新标为未读、收藏
- OPML 导入导出
- JSON 全量备份导入导出，格式与 Android MRSS 兼容
- GitHub Gist 同步备份：上传当前备份或从 Gist 下载恢复

## 数据位置

Windows 默认保存到：

```text
%APPDATA%\MRSS\mrss.db
```

## 启动

开发调试：

```powershell
cd desktop\MRSS
python modern_gui.py
```

正式使用安装包：

```text
desktop\MRSS\installer-output\MRSS-Setup-0.1.0.exe
```

安装后直接打开 `MRSS.exe`，它是独立窗口客户端。

## GitHub Gist 同步

在界面点击 `GitHub Gist`：

- `push`：把当前本地 JSON 备份上传到 Gist。首次上传可留空 Gist ID。
- `pull`：从指定 Gist 文件下载备份并恢复到本地。

Token 需要 GitHub `gist` 权限。建议使用私有 Gist。

## 与 Android 同步

电脑端和手机端使用相同 JSON 备份结构：

- 电脑端导出的 `mrss-backup.json` 可在 Android MRSS 中恢复。
- Android MRSS 导出的备份也可在电脑端导入。
- Gist 可作为两端的中转备份位置。
