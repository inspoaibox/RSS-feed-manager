# API 接口文档

客户端只需要调用公开翻译接口；管理员先在后台创建 API Key，再交给客户端使用。

完整 Swagger 文档：`/docs`

OpenAPI JSON：`/openapi.json`

## 1. 调用流程

1. 管理员登录 `POST /admin/login`，获得 JWT Token。
2. 管理员创建 API Key：`POST /admin/api-keys`。
3. 客户端携带 `X-API-Key` 调用 `POST /translate`。
4. 服务按请求中的 `model` 直接调用对应本地模型；不会自动切换备用模型。
5. 成功和已认证失败都会写入调用日志，用于统计、限流和耗时分析。

## 2. 公共翻译接口

**端点：** `POST /translate`

**认证：** API Key，请求头 `X-API-Key: sk_xxx`

**Content-Type：** `application/json`

### 请求示例

```bash
curl -X POST "https://fanyi.aboen.com/translate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_your_api_key" \
  -d '{
    "text": "Hello, world!",
    "source_lang": "en",
    "target_lang": "zh",
    "model": "argos"
  }'
```

### 请求字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `text` | 是 | 待翻译文本，不能为空；会尽量保留换行、空格、Markdown、HTML、JSON/YAML 等结构。 |
| `source_lang` | 是 | 源语言代码，例如 `en`、`zh`。 |
| `target_lang` | 是 | 目标语言代码，不能和源语言相同。 |
| `model` | 否 | 指定模型 ID；不传时使用系统默认模型。 |

### 响应示例

```json
{
  "translated_text": "你好，世界！",
  "model_used": "argos",
  "source_lang": "en",
  "target_lang": "zh",
  "success": true,
  "model_backend": "argos",
  "actual_model_name": "en-zh",
  "timing": {
    "backend": "argos",
    "actual_model_name": "en-zh",
    "model_load_ms": 0.12,
    "inference_ms": 8.43,
    "format_ms": 0.31,
    "segment_count": 1,
    "batch_count": 0
  }
}
```

## 3. 模型 ID

| model | 说明 | 使用条件 |
| --- | --- | --- |
| `argos` | 轻量级离线翻译 | 需安装对应 Argos 语言包。 |
| `marian` | Helsinki-NLP Opus-MT | 需下载对应语言对模型；可转换 CTranslate2 int8 后由 `MARIAN_BACKEND=auto` 优先调用。 |
| `m2m100` | facebook/m2m100_418M | 需下载标准 M2M100 模型；可转换 CTranslate2 int8 后由 `M2M100_BACKEND=auto` 优先调用。 |
| `m2m100_1_2b` | facebook/m2m100_1.2B | 需下载 1.2B 模型；可转换 CTranslate2，但转换和本地推理资源占用更高。 |
| `nllb` | facebook/nllb-200-distilled-600M | 需下载 NLLB 模型；可转换 CTranslate2 int8 后由 `NLLB_BACKEND=auto` 优先调用。 |

## 4. 支持的语言代码

实际可用语言对取决于对应模型或语言包是否已经下载，可在“模型管理”页面查看状态。

| 代码 | 语言 |
| --- | --- |
| `en` | 英语 |
| `zh` | 简体中文 |
| `zt` | 繁体中文，主要用于 Argos/NLLB 已安装或已支持场景 |
| `ja` | 日语 |
| `ko` | 韩语 |
| `fr` | 法语 |
| `de` | 德语 |
| `es` | 西班牙语 |
| `ru` | 俄语 |
| `ar`、`hi`、`th` 等 | NLLB 支持，M2M100 当前页面只开放常用语言。 |

## 5. 管理端接口

| 接口 | 认证 | 用途 |
| --- | --- | --- |
| `POST /admin/login` | 无 | 管理员登录，返回 JWT。 |
| `GET /admin/api-keys` | Bearer JWT | 查看 API Key 列表。 |
| `POST /admin/api-keys` | Bearer JWT | 创建 API Key。 |
| `DELETE /admin/api-keys/{id}` | Bearer JWT | 吊销 API Key，历史日志会保留归属。 |
| `GET /admin/models/status` | Bearer JWT | 查看模型、语言包、本地缓存完整性。 |
| `GET /admin/models/downloads/{task_id}` | Bearer JWT | 查询模型/语言包下载进度。 |
| `POST /admin/models/marian/convert-ct2` | Bearer JWT | 将已下载 MarianMT 转换为 CTranslate2 本地模型。 |
| `POST /admin/models/m2m100/convert-ct2` | Bearer JWT | 将已下载 M2M100 标准模型转换为 CTranslate2 本地模型。 |
| `POST /admin/models/m2m100-large/convert-ct2` | Bearer JWT | 将已下载 M2M100 1.2B 模型转换为 CTranslate2 本地模型。 |
| `POST /admin/models/nllb/convert-ct2` | Bearer JWT | 将已下载 NLLB 模型转换为 CTranslate2 本地模型。 |

## 6. 速率限制

每个 API Key 有独立限流，默认 `100` 请求 / `3600` 秒周期；请求数和周期都可在系统设置中调整。已认证的成功与失败翻译请求都会计入窗口。

## 7. 错误返回

错误响应使用 FastAPI 标准结构，主体通常为：

```json
{
  "detail": "错误说明"
}
```

| 状态码 | 说明 |
| --- | --- |
| `400` | 不支持的模型、语言对不可用、源语言和目标语言相同。 |
| `401` | 缺少 API Key、API Key 无效或已过期。 |
| `422` | JSON 字段缺失、类型错误或 `text` 为空。 |
| `429` | 超过 API Key 速率限制。 |
| `500` | 模型未初始化或服务器内部错误。 |
