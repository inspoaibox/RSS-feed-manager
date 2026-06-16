# 翻译范围功能 - 前端显示修复

## 修复时间
2026-06-16

## 问题描述

当订阅源设置为"只翻译标题"时，前端显示存在以下问题：

1. **正文显示空白**：打开文章详情页时，即使显示"已翻译"，正文也是空白的
2. **必须点击"原文"才能看到内容**：用户需要手动切换到"原文"才能看到正文
3. **无法重新翻译**：右上角的"翻译"按钮显示已完成状态，无法点击重新翻译标题+正文

## 根本原因

前端逻辑问题：

1. **第749行**：判断 `selectedArticle.translation` 存在就认为有翻译
2. **第807行**：如果 `showingTranslation` 为 true，直接显示 `translatedData.content`
3. **第707行**：`translationStatus === 'completed'` 时禁用翻译按钮

**结果**：当只翻译标题时，`translation` 字段存在但 `content` 为空，导致显示空白。

## 修复方案

### 修复 1：正文显示逻辑

**文件**：`frontend/src/pages/HomePage.tsx`

**修改前**：
```typescript
const showingTranslation = selectedArticle.translation && showTranslation

{showingTranslation ? (
  <div dangerouslySetInnerHTML={{ __html: translatedData.content }} />
) : (
  <div dangerouslySetInnerHTML={{ __html: selectedArticle.content }} />
)}
```

**修改后**：
```typescript
const hasTranslatedContent = translatedData.content && translatedData.content.trim() !== ''
const hasTranslatedTitle = translatedData.title && translatedData.title.trim() !== ''
const showingTranslation = selectedArticle.translation && showTranslation && (hasTranslatedTitle || hasTranslatedContent)

{showingTranslation && hasTranslatedContent ? (
  <div dangerouslySetInnerHTML={{ __html: translatedData.content }} />
) : (
  <div dangerouslySetInnerHTML={{ __html: selectedArticle.full_content || selectedArticle.content || '' }} />
)}
```

**关键改进**：
- 检查 `hasTranslatedContent` 是否真的有内容（非空字符串）
- 只有当翻译的正文存在且不为空时，才显示翻译的正文
- 否则始终显示原文正文

### 修复 2：标题显示逻辑

**修改后**：
```typescript
<h1>
  {showingTranslation && hasTranslatedTitle ? translatedData.title : selectedArticle.title}
</h1>
```

**关键改进**：
- 检查 `hasTranslatedTitle` 是否真的有翻译标题
- 只有当翻译标题存在且不为空时，才显示翻译标题

### 修复 3："译文/原文"按钮显示逻辑

**修改前**：
```typescript
{selectedArticle.translation && (
  <div>译文/原文按钮</div>
)}
```

**修改后**：
```typescript
{selectedArticle.translation && (hasTranslatedTitle || hasTranslatedContent) && (
  <div>译文/原文按钮</div>
)}
```

**关键改进**：
- 只有当标题或正文至少有一个被翻译时，才显示切换按钮
- 如果两者都为空（虽然不太可能），不显示按钮

### 修复 4：翻译按钮逻辑

**修改前**：
```typescript
const translationBusy = translateMutation.isPending || isTranslationActive(translationStatus)

// 按钮始终被禁用，即使是 completed 状态
```

**修改后**：
```typescript
const translationBusy = translateMutation.isPending || (translationStatus === 'queued' || translationStatus === 'translating')

// 按钮文本逻辑
let buttonTitle = '翻译'
if (translationBusy) {
  buttonTitle = getTranslationStatusText(translationStatus)
} else if (translationStatus === 'failed') {
  buttonTitle = '重新翻译'
} else if (translationStatus === 'completed' && !hasTranslatedContent) {
  buttonTitle = '翻译正文'  // 只翻译了标题，提示可以翻译正文
} else if (translationStatus === 'completed') {
  buttonTitle = '重新翻译'  // 已完成，可以重新翻译
}
```

**关键改进**：
- 只有在 `queued` 或 `translating` 状态时才禁用按钮
- `completed` 和 `failed` 状态下，按钮可点击
- 智能提示文字：
  - 只翻译了标题 → "翻译正文"
  - 已完成完整翻译 → "重新翻译"
  - 翻译失败 → "重新翻译"

## 用户体验改进

### 修复前的用户体验
1. ❌ 打开只翻译标题的文章 → 看到空白正文 → 困惑
2. ❌ 必须点击"原文"按钮 → 才能看到正文 → 额外操作
3. ❌ 想翻译完整文章 → 发现按钮不可点击 → 无法操作

### 修复后的用户体验
1. ✅ 打开只翻译标题的文章 → 标题显示译文，正文显示原文 → 符合预期
2. ✅ 可以看到翻译的标题 → 如果需要，点击"原文"查看原标题
3. ✅ 右上角显示"翻译正文"按钮 → 点击可以翻译完整文章（标题+正文）
4. ✅ 如果已完整翻译 → 显示"重新翻译"，可以再次翻译

## 测试场景

### 场景 1：只翻译标题的文章
**操作**：打开一篇只翻译了标题的文章

**预期结果**：
- ✅ 标题显示译文
- ✅ 正文显示原文（不是空白）
- ✅ 右上角显示"翻译正文"按钮（可点击）

### 场景 2：完整翻译的文章
**操作**：打开一篇标题+正文都翻译的文章

**预期结果**：
- ✅ 默认显示译文（标题和正文）
- ✅ 可以点击"原文"按钮切换到原文
- ✅ 右上角显示"重新翻译"按钮（可点击）

### 场景 3：重新翻译
**操作**：在只翻译标题的文章上点击"翻译正文"

**预期结果**：
- ✅ 发送翻译请求
- ✅ 按钮显示加载状态
- ✅ 翻译完成后，正文显示译文

### 场景 4：翻译失败
**操作**：翻译失败的文章

**预期结果**：
- ✅ 显示"翻译失败"状态
- ✅ 右上角显示"重新翻译"按钮（可点击）
- ✅ 点击可以重新尝试翻译

## 技术细节

### 翻译数据结构
```json
{
  "translation": "{\"title\":\"译文标题\",\"content\":\"译文正文\"}",
  "translation_status": "completed"
}
```

- **只翻译标题**：`content` 为空字符串
- **完整翻译**：`title` 和 `content` 都有值

### 判断逻辑
```typescript
// 检查是否有翻译内容
const hasTranslatedContent = translatedData.content && translatedData.content.trim() !== ''
const hasTranslatedTitle = translatedData.title && translatedData.title.trim() !== ''

// 根据实际内容决定显示什么
if (hasTranslatedContent) {
  // 显示译文正文
} else {
  // 显示原文正文
}
```

## 相关文件

### 前端
- `frontend/src/pages/HomePage.tsx` - 文章详情页显示逻辑

## 部署步骤

### 1. 提交代码
```bash
git add frontend/src/pages/HomePage.tsx
git commit -m "修复只翻译标题时的显示问题"
git push
```

### 2. 服务器更新
```bash
docker compose --profile browser -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production pull
docker compose --profile browser -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d
```

### 3. 验证
1. 创建一个新订阅源，设置为"只翻译标题"
2. 抓取文章
3. 打开文章详情页
4. 验证标题显示译文，正文显示原文
5. 点击"翻译正文"按钮，验证可以翻译完整文章

---

**修复状态**: ✅ 已完成  
**测试状态**: ⏳ 待部署验证  
**文档状态**: ✅ 已完成

**开发者**: Claude Code  
**完成时间**: 2026-06-16
