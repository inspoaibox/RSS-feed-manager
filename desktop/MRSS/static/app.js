const state = {
  categories: [],
  feeds: [],
  stats: {},
  articles: [],
  total: 0,
  offset: 0,
  scope: { type: 'all', id: null, title: '全部文章' },
  currentArticle: null,
}

const $ = (id) => document.getElementById(id)

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({ error: response.statusText }))
    throw new Error(data.error || response.statusText)
  }
  return response.json()
}

async function init() {
  bindEvents()
  await loadSummary()
  await loadArticles(false)
}

function bindEvents() {
  $('addFeedBtn').onclick = addFeed
  $('refreshBtn').onclick = refresh
  $('searchBtn').onclick = () => loadArticles(false)
  $('loadMoreBtn').onclick = () => loadArticles(true)
  $('markAllReadBtn').onclick = markAllRead
  $('addCategoryBtn').onclick = addCategory
  $('exportBtn').onclick = exportBackup
  $('importBtn').onclick = () => pickFile('.json', importBackup)
  $('importOpmlBtn').onclick = () => pickFile('.opml,.xml', importOpml)
  $('gistBtn').onclick = showGistMenu
  for (const id of ['unreadOnly', 'favoriteOnly', 'descending', 'sortSelect', 'dateSelect']) {
    $(id).onchange = () => loadArticles(false)
  }
  $('searchInput').onkeydown = (event) => {
    if (event.key === 'Enter') loadArticles(false)
  }
  $('favoriteArticleBtn').onclick = toggleFavorite
  $('unreadArticleBtn').onclick = markCurrentUnread
  $('closeArticleBtn').onclick = () => $('articleDialog').close()
  $('openArticleBtn').onclick = () => {
    if (state.currentArticle?.link) window.open(state.currentArticle.link, '_blank')
  }
}

async function loadSummary() {
  const summary = await api('/api/summary')
  state.categories = summary.categories
  state.feeds = summary.feeds
  state.stats = summary.stats
  renderSidebar()
}

function renderSidebar() {
  $('allCount').textContent = state.stats.unreadCount || 0
  document.querySelector('[data-scope="all"]').classList.toggle('active', state.scope.type === 'all')
  document.querySelector('[data-scope="all"]').onclick = () => selectScope('all', null, '全部文章')

  const categoryList = $('categoryList')
  categoryList.innerHTML = ''
  for (const category of state.categories) {
    const categoryButton = button('category-item', `${category.name}`, category.unread_count || category.feed_count || 0)
    categoryButton.classList.toggle('active', state.scope.type === 'category' && state.scope.id === category.id)
    categoryButton.onclick = () => selectScope('category', category.id, category.name)
    categoryButton.oncontextmenu = (event) => {
      event.preventDefault()
      categoryActions(category)
    }
    categoryList.appendChild(categoryButton)
    for (const feed of state.feeds.filter((item) => item.category_id === category.id)) {
      categoryList.appendChild(feedButton(feed))
    }
  }

  const uncategorized = $('uncategorizedList')
  uncategorized.innerHTML = ''
  for (const feed of state.feeds.filter((item) => !item.category_id)) {
    uncategorized.appendChild(feedButton(feed))
  }
}

function feedButton(feed) {
  const item = button('feed-item', feed.title, feed.unread_count || '')
  item.classList.toggle('active', state.scope.type === 'feed' && state.scope.id === feed.id)
  item.onclick = () => selectScope('feed', feed.id, feed.title)
  item.oncontextmenu = (event) => {
    event.preventDefault()
    feedActions(feed)
  }
  return item
}

function button(className, label, count) {
  const el = document.createElement('button')
  el.className = className
  el.innerHTML = `<span>${escapeHtml(label)}</span><span>${count || ''}</span>`
  return el
}

async function selectScope(type, id, title) {
  state.scope = { type, id, title }
  $('scopeTitle').textContent = title
  $('scopeMeta').textContent = type === 'all' ? '全部分类与订阅源' : type === 'category' ? '当前分类' : '当前订阅源'
  renderSidebar()
  await loadArticles(false)
}

function queryParams(append) {
  const params = new URLSearchParams()
  if (state.scope.type === 'feed') params.set('feed_id', state.scope.id)
  if (state.scope.type === 'category') params.set('category_id', state.scope.id)
  if ($('unreadOnly').checked) params.set('unread', '1')
  if ($('favoriteOnly').checked) params.set('favorite', '1')
  params.set('desc', $('descending').checked ? '1' : '0')
  params.set('sort', $('sortSelect').value)
  params.set('date', $('dateSelect').value)
  params.set('q', $('searchInput').value.trim())
  params.set('limit', '50')
  params.set('offset', append ? String(state.offset) : '0')
  return params
}

async function loadArticles(append) {
  const data = await api(`/api/articles?${queryParams(append)}`)
  if (!append) state.articles = []
  state.articles.push(...data.items)
  state.total = data.total
  state.offset = state.articles.length
  renderArticles()
}

function renderArticles() {
  $('status').textContent = state.total === 0
    ? '暂无文章。添加或导入订阅后，MRSS 会在电脑本地抓取和保存。'
    : `已显示 ${state.offset} / ${state.total} 篇，当前列表未读 ${state.articles.filter((a) => !a.is_read).length} 篇`
  $('loadMoreBtn').style.display = state.offset < state.total ? 'block' : 'none'
  const box = $('articles')
  box.innerHTML = ''
  for (const article of state.articles) {
    const card = document.createElement('article')
    card.className = `article-card ${article.is_read ? 'read' : ''}`
    card.innerHTML = `
      <h2>${article.is_favorite ? '★ ' : ''}${escapeHtml(article.title)}</h2>
      <p>${escapeHtml(stripHtml(article.content || '').slice(0, 180))}</p>
      <div class="meta">${escapeHtml(article.feed_title || '')} · ${formatTime(article.published_at || article.created_at)}${article.author ? ' · ' + escapeHtml(article.author) : ''}</div>
    `
    card.onclick = () => openArticle(article)
    box.appendChild(card)
  }
}

async function openArticle(article) {
  state.currentArticle = article
  await api(`/api/articles/${article.id}/read`, { method: 'POST', body: JSON.stringify({ read: true }) })
  article.is_read = 1
  $('dialogTitle').textContent = article.title
  $('dialogMeta').textContent = `${article.feed_title || ''} · ${formatTime(article.published_at || article.created_at)}`
  $('dialogContent').innerHTML = article.content || ''
  $('favoriteArticleBtn').textContent = article.is_favorite ? '取消收藏' : '收藏'
  $('articleDialog').showModal()
  renderArticles()
  loadSummary().catch(console.error)
}

async function addFeed() {
  const url = prompt('RSS/Atom 链接')
  if (!url) return
  const interval = Number(prompt('同步间隔秒数', '3600') || 3600)
  const categoryId = state.scope.type === 'category' ? state.scope.id : null
  await api('/api/feeds', { method: 'POST', body: JSON.stringify({ url, category_id: categoryId, fetch_interval: interval }) })
  await loadSummary()
  await loadArticles(false)
}

async function refresh() {
  const payload = {}
  if (state.scope.type === 'feed') payload.feed_id = state.scope.id
  if (state.scope.type === 'category') payload.category_id = state.scope.id
  $('status').textContent = '正在刷新订阅...'
  const result = await api('/api/refresh', { method: 'POST', body: JSON.stringify(payload) })
  alert(`刷新完成：成功 ${result.success}，失败 ${result.failed}，新增 ${result.inserted}`)
  await loadSummary()
  await loadArticles(false)
}

async function addCategory() {
  const name = prompt('分类名称')
  if (!name) return
  await api('/api/categories', { method: 'POST', body: JSON.stringify({ name }) })
  await loadSummary()
}

async function categoryActions(category) {
  const action = prompt(`分类：${category.name}\n输入 rename 或 delete`, 'rename')
  if (action === 'rename') {
    const name = prompt('新分类名称', category.name)
    if (name) await api(`/api/categories/${category.id}`, { method: 'POST', body: JSON.stringify({ name }) })
  } else if (action === 'delete' && confirm('删除分类？分类内订阅会变为未分类。')) {
    await api(`/api/categories/${category.id}`, { method: 'DELETE' })
  }
  await loadSummary()
}

async function feedActions(feed) {
  const action = prompt(`订阅：${feed.title}\n输入 rename / interval / active / delete`, 'rename')
  const data = { title: feed.title, category_id: feed.category_id, fetch_interval: feed.fetch_interval, active: !!feed.is_active }
  if (action === 'rename') {
    const title = prompt('新标题', feed.title)
    if (!title) return
    data.title = title
    await api(`/api/feeds/${feed.id}`, { method: 'POST', body: JSON.stringify(data) })
  } else if (action === 'interval') {
    data.fetch_interval = Number(prompt('同步间隔秒数', feed.fetch_interval) || feed.fetch_interval)
    await api(`/api/feeds/${feed.id}`, { method: 'POST', body: JSON.stringify(data) })
  } else if (action === 'active') {
    data.active = !feed.is_active
    await api(`/api/feeds/${feed.id}`, { method: 'POST', body: JSON.stringify(data) })
  } else if (action === 'delete' && confirm('删除订阅及其本地文章？')) {
    await api(`/api/feeds/${feed.id}`, { method: 'DELETE' })
  }
  await loadSummary()
  await loadArticles(false)
}

async function markAllRead() {
  const payload = {}
  if (state.scope.type === 'feed') payload.feed_id = state.scope.id
  if (state.scope.type === 'category') payload.category_id = state.scope.id
  const result = await api('/api/articles/mark-all-read', { method: 'POST', body: JSON.stringify(payload) })
  alert(`已标记 ${result.count} 篇文章`)
  await loadSummary()
  await loadArticles(false)
}

async function toggleFavorite() {
  if (!state.currentArticle) return
  const result = await api(`/api/articles/${state.currentArticle.id}/favorite`, { method: 'POST', body: '{}' })
  state.currentArticle.is_favorite = result.favorite ? 1 : 0
  $('favoriteArticleBtn').textContent = result.favorite ? '取消收藏' : '收藏'
  renderArticles()
}

async function markCurrentUnread() {
  if (!state.currentArticle) return
  await api(`/api/articles/${state.currentArticle.id}/read`, { method: 'POST', body: JSON.stringify({ read: false }) })
  state.currentArticle.is_read = 0
  $('articleDialog').close()
  await loadSummary()
  renderArticles()
}

async function exportBackup() {
  const backup = await api('/api/backup/export')
  download('mrss-backup.json', JSON.stringify(backup, null, 2), 'application/json')
}

function importBackup(text) {
  return api('/api/backup/restore', { method: 'POST', body: text }).then(async () => {
    await loadSummary()
    await loadArticles(false)
    alert('备份已恢复')
  })
}

function importOpml(text) {
  return api('/api/opml/import', { method: 'POST', body: JSON.stringify({ content: text }) }).then(async (result) => {
    await loadSummary()
    alert(`已导入 ${result.imported} 个订阅`)
  })
}

async function showGistMenu() {
  const action = prompt('GitHub Gist 同步：输入 push 上传，pull 下载恢复', 'push')
  if (!action) return
  const token = prompt('GitHub Token（需要 gist 权限）')
  if (!token) return
  const gist_id = prompt('Gist ID（首次上传可留空）') || ''
  const filename = prompt('文件名', 'mrss-backup.json') || 'mrss-backup.json'
  if (action === 'push') {
    const result = await api('/api/gist/push', { method: 'POST', body: JSON.stringify({ token, gist_id, filename }) })
    alert(`已上传到 Gist：${result.gist_id}`)
  } else if (action === 'pull' && confirm('从 Gist 下载会覆盖当前本地数据，继续？')) {
    await api('/api/gist/pull', { method: 'POST', body: JSON.stringify({ token, gist_id, filename }) })
    await loadSummary()
    await loadArticles(false)
    alert('已从 Gist 恢复')
  }
}

function pickFile(accept, handler) {
  const input = $('fileInput')
  input.accept = accept
  input.onchange = () => {
    const file = input.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => handler(String(reader.result)).catch((error) => alert(error.message))
    reader.readAsText(file, 'utf-8')
    input.value = ''
  }
  input.click()
}

function download(filename, content, type) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function formatTime(value) {
  if (!value) return ''
  return new Date(Number(value)).toLocaleString()
}

function stripHtml(html) {
  const div = document.createElement('div')
  div.innerHTML = html
  return div.textContent || div.innerText || ''
}

function escapeHtml(text) {
  return String(text || '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }[char]))
}

init().catch((error) => {
  console.error(error)
  $('status').textContent = error.message
})
