<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { api } from '../api'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ open: boolean; tripId: string; title: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const format = ref<'pdf' | 'png'>('pdf')
const status = ref<'idle' | 'creating' | 'running' | 'succeeded' | 'failed'>('idle')
const message = ref('')
const downloadUrl = ref('')
const note = ref('')
let timer = 0

function clearResult() {
  window.clearInterval(timer)
  status.value = 'idle'
  message.value = ''
  downloadUrl.value = ''
  note.value = ''
}

function reset() {
  clearResult()
  format.value = 'pdf'
}

watch(
  () => props.open,
  (open) => {
    if (open) reset()
    else window.clearInterval(timer)
  },
)

watch(format, () => {
  if (status.value === 'succeeded' || status.value === 'failed') clearResult()
})

async function poll(exportId: string) {
  try {
    const data = await api.getExport(exportId)
    if (data.status === 'succeeded') {
      window.clearInterval(timer)
      status.value = 'succeeded'
      downloadUrl.value = data.downloadUrl ? api.downloadExport(exportId) : ''
      note.value = data.error || ''
    } else if (data.status === 'failed') {
      window.clearInterval(timer)
      status.value = 'failed'
      message.value = data.error || '导出失败，请稍后重试'
    } else {
      message.value = '正在渲染版式与地图…'
    }
  } catch (e: any) {
    window.clearInterval(timer)
    status.value = 'failed'
    message.value = e.message || '查询导出状态失败'
  }
}

async function start() {
  if (status.value === 'creating' || status.value === 'running') return
  status.value = 'creating'
  message.value = '正在创建导出任务…'
  try {
    const job = await api.createExport(props.tripId, format.value)
    status.value = 'running'
    message.value = '正在渲染版式与地图…'
    timer = window.setInterval(() => poll(job.exportId), 1200)
    poll(job.exportId)
  } catch (e: any) {
    status.value = 'failed'
    message.value = e.message || '创建导出任务失败'
  }
}

function download() {
  if (!downloadUrl.value) return
  const a = document.createElement('a')
  a.href = downloadUrl.value
  a.target = '_blank'
  a.rel = 'noopener'
  a.click()
}

onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
      <div class="export-modal">
        <div class="export-head">
          <div>
            <div class="eyebrow">EXPORT</div>
            <h2>带走这份行程</h2>
            <p>{{ title }}</p>
          </div>
          <button class="close-btn" type="button" @click="emit('close')"><AppIcon name="x" :size="16" /></button>
        </div>

        <div class="format-grid">
          <button
            class="format-card"
            :class="{ active: format === 'pdf' }"
            type="button"
            @click="format = 'pdf'"
          >
            <span class="format-icon pdf"><AppIcon name="download" :size="19" /></span>
            <div>
              <b>PDF 行程单</b>
              <p>A4 排版，含地图、时间轴和预算，适合打印与分享。</p>
            </div>
            <span class="radio"><i></i></span>
          </button>
          <button
            class="format-card"
            :class="{ active: format === 'png' }"
            type="button"
            @click="format = 'png'"
          >
            <span class="format-icon png"><AppIcon name="download" :size="19" /></span>
            <div>
              <b>长图 PNG</b>
              <p>适合发微信 / 小红书，一屏看完整个行程。</p>
            </div>
            <span class="radio"><i></i></span>
          </button>
        </div>

        <div v-if="status === 'succeeded'" class="export-result success">
          <div class="result-icon"><AppIcon name="check" :size="20" /></div>
          <div>
            <b>文件已生成</b>
            <p>{{ note || '点击下方按钮下载，链接在本次会话内有效。' }}</p>
          </div>
          <button class="btn btn-teal" type="button" @click="download">
            <AppIcon name="download" :size="14" /> 下载
          </button>
        </div>

        <div v-else-if="status === 'failed'" class="export-result error">
          <div class="result-icon"><AppIcon name="info" :size="18" /></div>
          <div>
            <b>导出失败</b>
            <p>{{ message }}</p>
          </div>
          <button class="btn btn-ghost" type="button" @click="start">重试</button>
        </div>

        <div v-else-if="status !== 'idle'" class="export-result loading">
          <span class="loading-ring"></span>
          <div>
            <b>正在生成{{ format === 'pdf' ? ' PDF' : '长图' }}</b>
            <p>{{ message }}</p>
          </div>
        </div>

        <div v-if="status === 'idle' || status === 'failed'" class="export-actions">
          <button class="btn btn-primary" type="button" @click="start">
            <AppIcon name="sparkles" :size="14" /> 开始生成
          </button>
          <span>服务端渲染，通常需要 5–20 秒</span>
        </div>

        <div class="export-foot">
          <AppIcon name="info" :size="12" />
          导出内容为参考行程，价格与营业时间请以官方渠道为准。
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 70;
  background: rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.export-modal {
  width: min(550px, 100%);
  background: #fff;
  border-radius: 28px;
  box-shadow: 0 40px 100px rgba(0, 0, 0, 0.28);
  padding: 28px;
  animation: fadeUp 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

.export-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.export-head .eyebrow {
  font-size: 9px;
}

.export-head h2 {
  margin: 7px 0 0;
  font-size: 27px;
  letter-spacing: -0.045em;
  line-height: 1.1;
  font-weight: 600;
}

.export-head p {
  margin: 7px 0 0;
  color: var(--muted);
  font-size: 11px;
  max-width: 390px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 0;
  background: var(--bg-soft);
  color: var(--muted);
  display: grid;
  place-items: center;
}

.close-btn:hover {
  background: #e8e8ed;
}

.format-grid {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 22px;
}

.format-card {
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  border: 1px solid transparent;
  background: var(--bg-soft);
  border-radius: 16px;
  padding: 14px;
  transition: 0.18s ease;
}

.format-card:hover {
  background: #f0f0f2;
}

.format-card.active {
  border-color: rgba(0, 113, 227, 0.5);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.08);
}

.format-icon {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.format-icon.pdf { background: #fff2f3; color: var(--rose); }
.format-icon.png { background: #e8f8f7; color: var(--teal); }

.format-card b {
  display: block;
  font-size: 12.5px;
  font-weight: 600;
}

.format-card p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 9.5px;
  line-height: 1.55;
}

.format-card .radio {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid #c7c7cc;
  margin-left: auto;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.format-card.active .radio {
  border-color: var(--blue);
}

.format-card.active .radio i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--blue);
}

.export-result {
  display: flex;
  align-items: center;
  gap: 11px;
  border-radius: 14px;
  padding: 13px;
  margin-top: 15px;
}

.export-result.success {
  background: #f0faf9;
}

.export-result.error {
  background: #fff2f3;
}

.export-result.loading {
  background: var(--bg-soft);
}

.result-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.success .result-icon { background: #d9f5f2; color: var(--teal); }
.error .result-icon { background: #ffe4e6; color: var(--rose); }

.export-result b {
  display: block;
  font-size: 11px;
  font-weight: 600;
}

.export-result p {
  margin: 3px 0 0;
  color: var(--muted);
  font-size: 9px;
  line-height: 1.55;
}

.export-result > .btn,
.export-result > div + .btn {
  margin-left: auto;
  flex-shrink: 0;
  padding: 8px 12px;
  font-size: 9.5px;
}

.loading-ring {
  width: 24px;
  height: 24px;
  border: 2px solid #e5e5ea;
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

.export-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
}

.export-actions .btn {
  padding: 12px 18px;
  font-size: 12px;
}

.export-actions span {
  color: var(--faint);
  font-size: 9px;
}

.export-foot {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  border-top: 1px solid #f0f0f2;
  margin-top: 17px;
  padding-top: 12px;
  color: #a1a1a6;
  font-size: 8.5px;
  line-height: 1.5;
}

@media (max-width: 600px) {
  .modal-backdrop {
    padding: 0;
    align-items: flex-end;
  }

  .export-modal {
    width: 100%;
    border-radius: 24px 24px 0 0;
    padding: 22px 18px;
  }
}
</style>
