<template>
  <div class="app">
    <header class="app-header">
      <h1 class="app-title">Quartz Layout 配置编辑器</h1>
      <div class="header-actions">
        <button class="ant-btn ant-btn-default" @click="importJson">
          <span class="ant-btn-icon">⤴</span> 导入
        </button>
        <button class="ant-btn ant-btn-primary" @click="exportJson">
          <span class="ant-btn-icon">⤵</span> 导出
        </button>
      </div>
    </header>

    <main class="app-main">
      <JsonForms
        :data="data"
        :schema="schema"
        :uischema="uischema"
        :renderers="renderers"
        @change="onChange"
      />
    </main>

    <!-- 隐藏的文件输入 -->
    <input
      ref="fileInput"
      type="file"
      accept=".json"
      style="display: none"
      @change="onFileSelected"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, markRaw } from 'vue'
import { JsonForms, type JsonFormsChangeEvent } from '@jsonforms/vue'
import { vanillaRenderers } from '@jsonforms/vue-vanilla'
import { layoutSchema } from './schemas/layout.schema'
import { layoutUiSchema } from './schemas/layout.uischema'
import { layoutData } from './data/layout.data'

const renderers = markRaw([...vanillaRenderers])
const schema = layoutSchema
const uischema = layoutUiSchema

const data = ref(structuredClone(layoutData))
const fileInput = ref<HTMLInputElement | null>(null)

function onChange(event: JsonFormsChangeEvent) {
  data.value = event.data
}

function exportJson() {
  const json = JSON.stringify(data.value, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'quartz.layout.json'
  a.click()
  URL.revokeObjectURL(url)
}

function importJson() {
  fileInput.value?.click()
}

function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const parsed = JSON.parse(e.target?.result as string)
      data.value = parsed
    } catch (err) {
      alert('JSON 解析失败：' + (err as Error).message)
    }
  }
  reader.readAsText(file)
  input.value = ''
}
</script>

<style>
/* =============================================
   Ant Design 风格 CSS — 覆盖 JSONForms Vanilla
   ============================================= */

:root {
  --ant-primary: #1677ff;
  --ant-primary-hover: #4096ff;
  --ant-primary-active: #0958d9;
  --ant-primary-bg: #e6f4ff;
  --ant-border: #d9d9d9;
  --ant-border-focus: var(--ant-primary);
  --ant-text: rgba(0, 0, 0, 0.88);
  --ant-text-secondary: rgba(0, 0, 0, 0.65);
  --ant-text-desc: rgba(0, 0, 0, 0.45);
  --ant-bg: #ffffff;
  --ant-bg-hover: #fafafa;
  --ant-bg-layout: #f5f5f5;
  --ant-radius: 6px;
  --ant-radius-sm: 4px;
  --ant-font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --ant-font-size: 14px;
  --ant-font-size-sm: 12px;
  --ant-shadow-focus: 0 0 0 2px rgba(5, 145, 255, 0.1);
}

/* === Global === */
body {
  margin: 0;
  background: var(--ant-bg-layout);
  font-family: var(--ant-font);
  font-size: var(--ant-font-size);
  color: var(--ant-text);
  -webkit-font-smoothing: antialiased;
}

/* === App Layout === */
.app {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.app-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  color: var(--ant-text);
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* === Ant Design Buttons === */
.ant-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 15px;
  font-size: var(--ant-font-size);
  line-height: 1.5714;
  border-radius: var(--ant-radius);
  border: 1px solid var(--ant-border);
  background: var(--ant-bg);
  color: var(--ant-text);
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}

.ant-btn:hover {
  color: var(--ant-primary);
  border-color: var(--ant-primary-hover);
}

.ant-btn:active {
  color: var(--ant-primary-active);
  border-color: var(--ant-primary-active);
}

.ant-btn-primary {
  background: var(--ant-primary);
  color: #fff;
  border-color: var(--ant-primary);
}

.ant-btn-primary:hover {
  background: var(--ant-primary-hover);
  border-color: var(--ant-primary-hover);
  color: #fff;
}

.ant-btn-primary:active {
  background: var(--ant-primary-active);
  border-color: var(--ant-primary-active);
  color: #fff;
}

.ant-btn-icon {
  font-size: 16px;
  line-height: 1;
}

/* === Main Card === */
.app-main {
  background: var(--ant-bg);
  border-radius: var(--ant-radius);
  border: 1px solid var(--ant-border);
  padding: 24px;
}

/* =============================================
   JSONForms Vanilla 覆盖 — Ant Design 风格
   ============================================= */

/* --- Categorization Tabs (Ant Tabs) --- */
.categorization {
  display: flex;
  flex-direction: column;
}

.categorization-category {
  display: flex;
  border-bottom: 2px solid var(--ant-border);
  margin-bottom: 0;
  gap: 0;
}

.categorization-category button {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 8px 20px;
  cursor: pointer;
  font-size: var(--ant-font-size);
  color: var(--ant-text-secondary);
  transition: color 0.3s, border-color 0.3s;
  outline: none;
}

.categorization-category button:hover {
  color: var(--ant-primary-hover);
}

.categorization-category button.categorization-selected {
  color: var(--ant-primary);
  border-bottom-color: var(--ant-primary);
  font-weight: 500;
}

.categorization-category button label {
  cursor: pointer;
}

.categorization-panel {
  padding: 16px 0;
}

/* --- Vertical Layout --- */
.vertical-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vertical-layout-item {
  flex: 1;
}

/* --- Group Layout (Ant Card-like) --- */
.group-layout {
  border: 1px solid #f0f0f0;
  border-radius: var(--ant-radius);
  padding: 16px;
  background: var(--ant-bg);
  margin: 0;
}

.group-layout > label {
  display: block;
  font-size: var(--ant-font-size);
  font-weight: 500;
  color: var(--ant-text);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

/* --- Control (Ant Form Item) --- */
.control {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
}

.control > label {
  font-size: var(--ant-font-size);
  color: var(--ant-text);
  font-weight: 400;
  line-height: 1.5714;
}

.control > .description {
  font-size: var(--ant-font-size-sm);
  color: var(--ant-text-desc);
  line-height: 1.5;
}

.control > .error {
  font-size: var(--ant-font-size-sm);
  color: #ff4d4f;
}

/* --- Input / Select (Ant Input) --- */
.control .wrapper {
  display: flex;
  align-items: center;
}

.control .wrapper > input,
.control .wrapper > select,
.control .wrapper > textarea {
  flex: 1;
  padding: 4px 11px;
  font-size: var(--ant-font-size);
  line-height: 1.5714;
  color: var(--ant-text);
  background: var(--ant-bg);
  border: 1px solid var(--ant-border);
  border-radius: var(--ant-radius);
  transition: all 0.2s;
  outline: none;
  min-height: 32px;
  box-sizing: border-box;
}

.control .wrapper > input:hover,
.control .wrapper > select:hover,
.control .wrapper > textarea:hover {
  border-color: var(--ant-primary-hover);
}

.control .wrapper > input:focus,
.control .wrapper > select:focus,
.control .wrapper > textarea:focus {
  border-color: var(--ant-border-focus);
  box-shadow: var(--ant-shadow-focus);
}

.control .wrapper > input::placeholder {
  color: var(--ant-text-desc);
}

/* --- Checkbox (Ant Checkbox) --- */
.control .wrapper > input[type='checkbox'] {
  width: 16px;
  height: 16px;
  border-radius: var(--ant-radius-sm);
  border: 1px solid var(--ant-border);
  accent-color: var(--ant-primary);
  cursor: pointer;
  flex: none;
  margin-right: 8px;
  vertical-align: middle;
}

/* --- Array List (Ant Card List) --- */
.array-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.array-list > label {
  font-size: var(--ant-font-size);
  font-weight: 500;
  color: var(--ant-text);
}

.array-list-item-toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: stretch;
  margin: 0;
  background: var(--ant-bg-layout);
  border-radius: var(--ant-radius-sm);
  cursor: pointer;
  gap: 0;
  overflow: hidden;
}

.array-list-item-label {
  background: transparent;
  flex: 1;
  padding-left: 12px;
  height: auto;
  line-height: 32px;
  font-size: var(--ant-font-size-sm);
  color: var(--ant-text-secondary);
  cursor: pointer;
  border: none;
}

.array-list-item-label:hover {
  background: #e8e8e8;
}

.array-list-item-toolbar > button {
  padding: 4px 8px;
  font-size: var(--ant-font-size-sm);
  color: var(--ant-text-secondary);
  background: transparent;
  border: none;
  border-left: 1px solid var(--ant-border);
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
  line-height: 32px;
}

.array-list-item-toolbar > button:hover {
  color: var(--ant-primary);
  background: var(--ant-primary-bg);
}

.array-list-item-toolbar > button:disabled {
  color: rgba(0, 0, 0, 0.25);
  cursor: not-allowed;
  background: transparent;
}

/* --- Array Item Content (Ant Collapse) --- */
.array-list-item-content {
  border: 1px solid #f0f0f0;
  border-radius: var(--ant-radius-sm);
  padding: 16px;
  margin: 0;
  background: var(--ant-bg);
}

.array-list-item-content.expanded {
  display: block;
  margin-bottom: 4px;
}

/* --- Array Add Button --- */
.array-list > button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 4px 15px;
  font-size: var(--ant-font-size);
  border: 1px dashed var(--ant-border);
  border-radius: var(--ant-radius);
  background: var(--ant-bg);
  color: var(--ant-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
}

.array-list > button:hover {
  color: var(--ant-primary);
  border-color: var(--ant-primary);
  background: var(--ant-primary-bg);
}

/* --- Horizontal Layout --- */
.horizontal-layout {
  display: flex;
  flex-direction: row;
  gap: 16px;
}

.horizontal-layout-item {
  flex: 1;
}

/* --- Label --- */
.label-layout {
  display: flex;
  align-items: center;
  margin: 8px 0;
}

.label-layout > label {
  font-size: var(--ant-font-size);
  color: var(--ant-text-secondary);
  font-weight: 400;
}

/* --- Error --- */
.error {
  color: #ff4d4f;
  font-size: var(--ant-font-size-sm);
}
</style>