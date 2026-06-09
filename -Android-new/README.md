# MRSS Mobile Android New

这是新的服务端驱动 Android 手机端，独立于现有 `android/MRSS` 本地单机客户端。

## 定位

- 服务端是唯一权威数据源。
- 手机端只缓存分类、订阅源、文章、翻译、摘要和阅读状态。
- 手机端不再抓取 RSS，也不再本地调用翻译服务。
- 手机端操作会通过服务端 API 写回并同步到其他端。

## 已接入的服务端接口

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/mobile/sync`
- `POST /api/v1/mobile/actions`
- `POST /api/v1/articles/{id}/translate`
- `POST /api/v1/articles/{id}/summarize`

## 构建

```powershell
cd "D:\website\RSS feed manager\-Android-new"
$env:ANDROID_HOME='D:\Android\Sdk'
& 'D:\Android\gradle\wrapper\dists\gradle-9.3.1-bin\23ovyewtku6u96viwx3xl3oks\gradle-9.3.1\bin\gradle.bat' assembleDebug
```
