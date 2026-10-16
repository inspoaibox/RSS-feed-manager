import js from '@eslint/js'
import tsParser from '@typescript-eslint/parser'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'

export default [
  { ignores: ['dist/**', 'node_modules/**', '*.backup', '.eslintrc.cjs'] },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { parser: tsParser, ecmaVersion: 'latest', sourceType: 'module',
                       globals: globals.browser },
    plugins: { '@typescript-eslint': tsPlugin, 'react-hooks': reactHooks,
               'react-refresh': reactRefresh },
    rules: { ...js.configs.recommended.rules, ...tsPlugin.configs.recommended.rules,
             ...reactHooks.configs.recommended.rules,
             // TypeScript checks names, including DOM and React type namespaces.
             'no-undef': 'off',
             'react-refresh/only-export-components': ['warn', { allowConstantExport: true }] },
  },
]
