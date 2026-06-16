// Patch script to add translation scope checkboxes to SettingsPage.tsx
const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'frontend', 'src', 'pages', 'SettingsPage.tsx');
let content = fs.readFileSync(filePath, 'utf8');

// Add translation scope checkboxes after target language selection in add form
const addFormPattern = /(\s+{newFeedTranslateMethod !== 'none' && \(\s+<select[\s\S]*?<\/select>\s+\)\})/;
const addFormReplacement = `$1
            {newFeedTranslateMethod !== 'none' && (
              <div className="flex items-center gap-2 p-2 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded">
                <span className="text-sm dark:text-blue-200">翻译范围:</span>
                <label className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={newFeedTranslateTitle}
                    onChange={(e) => {
                      const checked = e.target.checked
                      if (!checked && !newFeedTranslateContent) {
                        setMessage({ type: 'error', text: '至少需要翻译标题或正文' })
                        return
                      }
                      setNewFeedTranslateTitle(checked)
                    }}
                  />
                  <span className="text-sm dark:text-blue-200">标题</span>
                </label>
                <label className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={newFeedTranslateContent}
                    onChange={(e) => {
                      const checked = e.target.checked
                      if (!checked && !newFeedTranslateTitle) {
                        setMessage({ type: 'error', text: '至少需要翻译标题或正文' })
                        return
                      }
                      setNewFeedTranslateContent(checked)
                    }}
                  />
                  <span className="text-sm dark:text-blue-200">正文</span>
                </label>
              </div>
            )}`;

// Apply patch
if (addFormPattern.test(content)) {
  content = content.replace(addFormPattern, addFormReplacement);
  fs.writeFileSync(filePath, content, 'utf8');
  console.log('Successfully patched add form translation scope UI');
} else {
  console.log('Add form pattern not found - manual edit required');
}
