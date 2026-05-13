# 桌面版打包检查清单

## 📋 构建前检查

### 环境准备

- [ ] Python 3.11+ 已安装
  ```bash
  python --version
  # 应显示 Python 3.11.x 或更高
  ```

- [ ] Node.js 18+ 已安装
  ```bash
  node --version
  # 应显示 v18.x.x 或更高
  ```

- [ ] Git 已安装（可选）
  ```bash
  git --version
  ```

- [ ] Inno Setup 已安装（可选，用于创建安装程序）
  - 路径：`C:\Program Files (x86)\Inno Setup 6\`

### 依赖安装

- [ ] Python 依赖已安装
  ```bash
  cd desktop/backend
  pip install -r requirements.txt
  ```

- [ ] 前端依赖已安装
  ```bash
  cd frontend
  npm install
  ```

- [ ] Playwright 浏览器已安装
  ```bash
  python -m playwright install chromium
  ```

## 🔧 构建步骤

### 1. 准备后端文件

- [ ] 复制 `backend/app/` 到 `desktop/backend/app/`
  ```bash
  xcopy /E /I /Y backend\app desktop\backend\app
  ```

- [ ] 保留桌面版特有文件
  - [ ] `desktop/backend/app/core/config_desktop.py`
  - [ ] `desktop/backend/app/core/deps_desktop.py`
  - [ ] `desktop/backend/app/scheduler/scheduler.py`
  - [ ] `desktop/backend/app/services/init_service.py`
  - [ ] `desktop/backend/app/api/v1/__init___desktop.py`
  - [ ] `desktop/backend/app/main_desktop.py`

- [ ] 替换文件
  - [ ] 用 `__init___desktop.py` 替换 `app/api/v1/__init__.py`
  - [ ] 用 `deps_desktop.py` 替换 `app/core/deps.py`
  - [ ] 用 `config_desktop.py` 替换 `app/core/config.py`

### 2. 检查数据库迁移

- [ ] 确认 Alembic 迁移兼容 SQLite
  - [ ] 移除 pgvector 相关迁移
  - [ ] 移除 PostgreSQL 特有语法

### 3. 构建前端

- [ ] 应用前端补丁
  ```bash
  cd desktop/build
  python patch_frontend.py
  ```

- [ ] 构建前端
  ```bash
  cd ../../frontend
  npm run build
  ```

- [ ] 复制构建文件到 desktop
  ```bash
  xcopy /E /I /Y dist ..\desktop\frontend
  ```

### 4. 打包可执行文件

- [ ] 运行 PyInstaller
  ```bash
  cd desktop/build
  pyinstaller main.spec --clean
  ```

- [ ] 检查输出
  - [ ] `desktop/dist/RSSManager/` 目录存在
  - [ ] `RSSManager.exe` 文件存在
  - [ ] 文件大小合理（150-400 MB）

### 5. 恢复前端

- [ ] 恢复原始前端文件
  ```bash
  cd desktop/build
  python patch_frontend.py restore
  ```

### 6. 创建安装程序（可选）

- [ ] 编译 Inno Setup 脚本
  ```bash
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" desktop\installer\setup.iss
  ```

- [ ] 检查输出
  - [ ] `desktop/installer/output/` 目录存在
  - [ ] `RSSManager-Setup-1.0.0.exe` 文件存在

## ✅ 测试清单

### 基础测试

- [ ] 可执行文件可以启动
  ```bash
  desktop\dist\RSSManager\RSSManager.exe
  ```

- [ ] 窗口正常显示
- [ ] 前端界面加载正常
- [ ] 无控制台错误

### 功能测试

#### 订阅源管理

- [ ] 添加订阅源
  - [ ] 输入 RSS URL
  - [ ] 选择分类
  - [ ] 设置同步间隔
  - [ ] 保存成功

- [ ] 编辑订阅源
  - [ ] 修改标题
  - [ ] 修改分类
  - [ ] 修改间隔
  - [ ] 保存成功

- [ ] 删除订阅源
  - [ ] 确认对话框
  - [ ] 删除成功

- [ ] 手动刷新
  - [ ] 点击刷新按钮
  - [ ] 显示加载状态
  - [ ] 获取新文章

- [ ] 自动刷新
  - [ ] 等待设定的间隔时间
  - [ ] 自动获取新文章
  - [ ] 后台运行正常

#### 文章管理

- [ ] 文章列表显示
  - [ ] 显示标题
  - [ ] 显示摘要
  - [ ] 显示时间
  - [ ] 显示已读状态

- [ ] 文章详情
  - [ ] 点击文章打开详情
  - [ ] 显示完整内容
  - [ ] 显示图片
  - [ ] 显示链接

- [ ] 标记已读/未读
  - [ ] 点击标记
  - [ ] 状态更新
  - [ ] 列表刷新

- [ ] 收藏/取消收藏
  - [ ] 点击收藏
  - [ ] 状态更新
  - [ ] 收藏列表显示

- [ ] 搜索文章
  - [ ] 输入关键词
  - [ ] 显示匹配结果
  - [ ] 高亮关键词

#### 分类管理

- [ ] 创建分类
  - [ ] 输入名称
  - [ ] 选择颜色
  - [ ] 保存成功

- [ ] 编辑分类
  - [ ] 修改名称
  - [ ] 修改颜色
  - [ ] 保存成功

- [ ] 删除分类
  - [ ] 确认对话框
  - [ ] 删除成功
  - [ ] 订阅源移到未分类

- [ ] 分类排序
  - [ ] 拖动排序
  - [ ] 顺序保存

#### 自定义规则

- [ ] 创建规则
  - [ ] 输入名称
  - [ ] 输入 URL
  - [ ] 配置选择器
  - [ ] 保存成功

- [ ] 执行规则
  - [ ] 手动执行
  - [ ] 获取内容
  - [ ] 创建文章

- [ ] 定时执行
  - [ ] 设置间隔
  - [ ] 自动执行
  - [ ] 后台运行

#### AI 功能

- [ ] 配置 AI 渠道
  - [ ] 选择提供商
  - [ ] 输入 API Key
  - [ ] 输入模型名称
  - [ ] 保存成功

- [ ] 文章翻译
  - [ ] 点击翻译按钮
  - [ ] 显示加载状态
  - [ ] 显示翻译结果
  - [ ] 翻译准确

- [ ] 文章摘要
  - [ ] 点击摘要按钮
  - [ ] 显示加载状态
  - [ ] 显示摘要结果
  - [ ] 摘要准确

- [ ] 关键词搜索
  - [ ] 输入关键词
  - [ ] 显示匹配文章
  - [ ] 结果相关

#### 备份恢复

- [ ] 导出 OPML
  - [ ] 点击导出
  - [ ] 选择保存位置
  - [ ] 文件生成成功

- [ ] 导入 OPML
  - [ ] 点击导入
  - [ ] 选择文件
  - [ ] 导入成功
  - [ ] 订阅源显示

- [ ] WebDAV 备份
  - [ ] 配置服务器
  - [ ] 点击备份
  - [ ] 上传成功

- [ ] WebDAV 恢复
  - [ ] 点击恢复
  - [ ] 下载成功
  - [ ] 数据恢复

#### 设置

- [ ] AI 设置
  - [ ] 添加渠道
  - [ ] 编辑渠道
  - [ ] 删除渠道
  - [ ] 设置默认

- [ ] 系统设置
  - [ ] 修改设置
  - [ ] 保存成功
  - [ ] 设置生效

- [ ] 通知设置
  - [ ] 启用/禁用
  - [ ] 设置保存

### 性能测试

- [ ] 启动时间
  - [ ] 首次启动 < 10 秒
  - [ ] 后续启动 < 5 秒

- [ ] 内存占用
  - [ ] 空闲时 < 300 MB
  - [ ] 使用时 < 500 MB

- [ ] CPU 占用
  - [ ] 空闲时 < 5%
  - [ ] 抓取时 < 30%

- [ ] 响应速度
  - [ ] 界面操作流畅
  - [ ] 无明显卡顿

### 压力测试

- [ ] 大量订阅源
  - [ ] 添加 100+ 订阅源
  - [ ] 应用正常运行
  - [ ] 刷新正常

- [ ] 大量文章
  - [ ] 10000+ 文章
  - [ ] 列表加载正常
  - [ ] 搜索正常

- [ ] 长时间运行
  - [ ] 运行 24 小时
  - [ ] 无内存泄漏
  - [ ] 定时任务正常

### 兼容性测试

- [ ] Windows 10
  - [ ] 安装成功
  - [ ] 运行正常

- [ ] Windows 11
  - [ ] 安装成功
  - [ ] 运行正常

- [ ] 不同分辨率
  - [ ] 1920x1080
  - [ ] 1366x768
  - [ ] 2560x1440

- [ ] 高 DPI
  - [ ] 125% 缩放
  - [ ] 150% 缩放
  - [ ] 200% 缩放

### 安装测试

- [ ] 全新安装
  - [ ] 运行安装程序
  - [ ] 选择安装路径
  - [ ] 安装成功
  - [ ] 快捷方式创建

- [ ] 升级安装
  - [ ] 安装旧版本
  - [ ] 添加测试数据
  - [ ] 安装新版本
  - [ ] 数据保留
  - [ ] 功能正常

- [ ] 卸载
  - [ ] 运行卸载程序
  - [ ] 卸载成功
  - [ ] 快捷方式删除
  - [ ] 数据保留（可选）

## 📝 发布前检查

### 文档

- [ ] README.md 完整
- [ ] QUICK_START.md 准确
- [ ] BUILD_GUIDE.md 详细
- [ ] USER_GUIDE.md 清晰
- [ ] CHANGELOG.md 更新

### 版本信息

- [ ] 版本号正确
  - [ ] `desktop/backend/app/core/config_desktop.py`
  - [ ] `desktop/installer/setup.iss`
  - [ ] `desktop/README.md`

- [ ] 更新日志完整
  - [ ] 新功能列表
  - [ ] Bug 修复列表
  - [ ] 已知问题列表

### 资源文件

- [ ] 应用图标
  - [ ] icon.ico 存在
  - [ ] 尺寸正确（256x256）
  - [ ] 格式正确

- [ ] 许可证
  - [ ] LICENSE.txt 存在
  - [ ] 内容正确

### 发布包

- [ ] 可执行文件
  - [ ] 文件完整
  - [ ] 大小合理
  - [ ] 可以运行

- [ ] 安装程序
  - [ ] 文件完整
  - [ ] 大小合理
  - [ ] 可以安装

- [ ] 压缩包（可选）
  - [ ] 包含所有文件
  - [ ] 解压后可运行

### GitHub Release

- [ ] 创建 Release
  - [ ] 版本标签
  - [ ] 发布说明
  - [ ] 上传文件

- [ ] 更新 README
  - [ ] 下载链接
  - [ ] 版本信息
  - [ ] 更新日志

## 🎉 完成

- [ ] 所有测试通过
- [ ] 文档完整
- [ ] 发布包准备就绪
- [ ] GitHub Release 创建

---

**检查日期**: ___________  
**检查人**: ___________  
**版本**: 1.0.0
