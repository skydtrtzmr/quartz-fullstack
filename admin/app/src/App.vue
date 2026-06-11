<template>
  <div class="app">
    <header class="app-header">
      <h1>Quartz Layout 配置编辑器</h1>
      <div class="actions">
        <button class="btn btn-import" @click="importJson">导入 JSON</button>
        <button class="btn btn-export" @click="exportJson">导出 JSON</button>
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
  // 重置 input 以便重复选择同一文件
  input.value = ''
}
</script>

<style>
/* === Global Reset === */
*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f5f5f5;
  color: #333;
}

/* === App Layout === */
.app {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e0e0e0;
}

.app-header h1 {
  font-size: 1.5rem;
  margin: 0;
  color: #1a1a1a;
}

.actions {
  display: flex;
  gap: 8px;
}

/* === Buttons === */
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-export {
  background: #4f46e5;
  color: white;
}

.btn-export:hover {
  background: #4338ca;
}

.btn-import {
  background: #e0e0e0;
  color: #333;
}

.btn-import:hover {
  background: #d0d0d0;
}

/* === JSONForms Vanilla Overrides === */
.app-main {
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* Categorization tabs */
.category-tab {
  padding: 8px 16px;
  border: 1px solid #d0d0d0;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  background: #f0f0f0;
  cursor: pointer;
  margin-right: 4px;
}

.category-tab.selected {
  background: white;
  border-bottom: 1px solid white;
  font-weight: 600;
}

/* Control labels */
.control label {
  font-weight: 500;
  margin-bottom: 4px;
  display: block;
  color: #555;
  font-size: 0.875rem;
}

/* Input styling */
.control input[type='text'],
.control input[type='number'],
.control select {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  font-size: 0.875rem;
  transition: border-color 0.2s;
}

.control input:focus,
.control select:focus {
  outline: none;
  border-color: #4f46e5;
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15);
}

/* Array styling */
.array-layout {
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  padding: 12px;
  margin: 8px 0;
  background: #fafafa;
}

.array-layout button {
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid #d0d0d0;
  background: white;
  cursor: pointer;
  font-size: 0.8rem;
}

.array-layout button:hover {
  background: #f0f0f0;
}

/* Object group */
.group-layout {
  margin: 8px 0;
  padding: 12px;
  border: 1px solid #eee;
  border-radius: 6px;
  background: #fcfcfc;
}

/* Checkbox */
.control input[type='checkbox'] {
  margin-right: 6px;
}

/* Vertical layout spacing */
.vertical-layout > * {
  margin-bottom: 12px;
}

.vertical-layout > *:last-child {
  margin-bottom: 0;
}
</style>
