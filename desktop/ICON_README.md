# 应用图标说明

## 图标要求

桌面版需要一个应用图标文件：

- **文件名**: `icon.ico`
- **位置**: `desktop/icon.ico`
- **格式**: Windows ICO 格式
- **尺寸**: 256x256 像素（推荐包含多个尺寸）

## 创建图标

### 方式一：在线工具

1. 访问 [ICO Convert](https://icoconvert.com/)
2. 上传 PNG 图片（256x256）
3. 选择输出尺寸：256, 128, 64, 48, 32, 16
4. 下载生成的 .ico 文件
5. 重命名为 `icon.ico`
6. 放置在 `desktop/` 目录

### 方式二：使用 ImageMagick

```bash
# 安装 ImageMagick
# Windows: https://imagemagick.org/script/download.php

# 转换 PNG 到 ICO
magick convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

### 方式三：使用 Python

```python
from PIL import Image

# 打开 PNG 图片
img = Image.open('icon.png')

# 调整大小并保存为 ICO
img.save('icon.ico', format='ICO', sizes=[
    (16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)
])
```

## 设计建议

### 图标内容

- 简洁明了，易于识别
- 与 RSS 相关的元素（如 RSS 图标、订阅符号）
- 使用品牌颜色
- 避免过于复杂的细节

### 颜色方案

推荐使用：
- 主色：蓝色（#3B82F6）- 代表科技、信息
- 辅色：橙色（#F97316）- RSS 标准颜色
- 背景：白色或渐变

### 示例设计

```
┌─────────────────┐
│                 │
│    ┌─────┐      │
│    │ RSS │      │  简单的 RSS 图标
│    └─────┘      │  + 文字标识
│                 │
└─────────────────┘
```

或

```
┌─────────────────┐
│                 │
│      )))        │  RSS 波纹图标
│     (( ))       │  简洁现代
│    (   )        │
│                 │
└─────────────────┘
```

## 临时方案

如果暂时没有图标，可以：

1. **使用默认图标**
   - PyInstaller 会使用默认的 Python 图标
   - 不影响功能，只是不够美观

2. **使用占位图标**
   - 创建简单的纯色图标
   - 后续再替换

3. **跳过图标**
   - 在 `main.spec` 中注释掉 `icon` 参数
   ```python
   # icon=str(desktop_dir / 'icon.ico') if (desktop_dir / 'icon.ico').exists() else None,
   icon=None,
   ```

## 应用图标

### PyInstaller

图标在 `desktop/build/main.spec` 中配置：

```python
exe = EXE(
    ...
    icon=str(desktop_dir / 'icon.ico'),
    ...
)
```

### Inno Setup

图标在 `desktop/installer/setup.iss` 中配置：

```ini
[Setup]
UninstallDisplayIcon={app}\{#MyAppExeName}

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
```

## 测试图标

构建后检查：

1. **可执行文件图标**
   - 查看 `desktop/dist/RSSManager/RSSManager.exe`
   - 应显示自定义图标

2. **快捷方式图标**
   - 安装后查看桌面快捷方式
   - 应显示自定义图标

3. **任务栏图标**
   - 运行应用
   - 查看任务栏图标
   - 应显示自定义图标

## 资源

### 图标设计工具

- [Figma](https://www.figma.com/) - 在线设计工具
- [Inkscape](https://inkscape.org/) - 免费矢量图形编辑器
- [GIMP](https://www.gimp.org/) - 免费图像编辑器

### 图标转换工具

- [ICO Convert](https://icoconvert.com/) - 在线转换
- [ConvertICO](https://convertico.com/) - 在线转换
- [ImageMagick](https://imagemagick.org/) - 命令行工具

### 图标资源

- [Flaticon](https://www.flaticon.com/) - 免费图标库
- [Icons8](https://icons8.com/) - 图标和插图
- [Font Awesome](https://fontawesome.com/) - 图标字体

## 注意事项

1. **版权**
   - 确保有权使用图标
   - 注明来源（如需要）

2. **文件大小**
   - ICO 文件不应过大（< 1MB）
   - 包含必要的尺寸即可

3. **透明度**
   - 使用透明背景
   - 避免白色背景（在深色主题下不美观）

4. **测试**
   - 在不同背景下测试
   - 在不同尺寸下测试
   - 在高 DPI 显示器上测试
