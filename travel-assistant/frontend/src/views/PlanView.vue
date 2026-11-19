<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { api, streamPlanRun } from '../api'
import type { PlanEvent } from '../types'

const route = useRoute()
const router = useRouter()
const runId = String(route.params.runId || '')
const progress = ref(4)
const stage = ref('normalize')
const message = ref('正在读取你的需求')
const error = ref('')
const finished = ref(false)
const dayPreview = ref<{ dayIndex: number; theme: string; count: number }[]>([])
let controller: AbortController | null = null
let redirectTimer = 0

const planMeta = computed(() => {
  try {
    return JSON.parse(sessionStorage.getItem('ta_last_plan') || '{}')
  } catch {
    return {}
  }
})

const stages = [
  { key: 'normalize', label: '理解需求', desc: '日期、人数、偏好' },
  { key: 'gather', label: '检索 POI', desc: '景点 · 餐饮 · 酒店' },
  { key: 'draft', label: '编排行程', desc: '按天与地理聚类' },
  { key: 'route', label: '计算路线', desc: '路程与交通方式' },
  { key: 'budget', label: '核算预算', desc: '分类明细与缓冲' },
]

const activeIndex = computed(() => {
  const idx = stages.findIndex((s) => s.key === stage.value)
  return idx < 0 ? 0 : idx
})

function handle(event: PlanEvent) {
  if (event.type === 'stage') {
    stage.value = event.stage
    progress.value = Math.max(progress.value, event.progress)
    message.value = event.message
  } else if (event.type === 'day') {
    dayPreview.value = event.days.map((d) => ({
      dayIndex: d.dayIndex,
      theme: d.theme,
      count: d.items.length,
    }))
    progress.value = Math.max(progress.value, 94)
    message.value = '正在整理每日安排与参考价'
  } else if (event.type === 'plan') {
    finished.value = true
    progress.value = 100
    message.value = '行程已生成，正在打开工作台'
    window.clearTimeout(redirectTimer)
    redirectTimer = window.setTimeout(() => {
      router.replace(`/trips/${event.tripId}`)
    }, 650)
  } else if (event.type === 'error') {
    error.value = event.message || '规划失败'
  }
}

async function start() {
  if (!runId) {
    error.value = '缺少规划任务 ID'
    return
  }
  controller = new AbortController()
  try {
    await api.session()
    await streamPlanRun(runId, handle, controller.signal)
    if (!finished.value && !error.value) {
      const info = await api.getRun(runId)
      if (info.status === 'succeeded' && info.tripId) {
        finished.value = true
        router.replace(`/trips/${info.tripId}`)
      } else if (info.status === 'failed') {
        error.value = info.error || '规划失败'
      }
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    error.value = e.message || '无法获取规划进度'
  }
}

onMounted(start)
onBeforeUnmount(() => {
  controller?.abort()
  window.clearTimeout(redirectTimer)
})
</script>

<template>
  <div class="page plan-page">
    <div class="plan-top">
      <router-link to="/" class="back-link"><AppIcon name="arrow-left" :size="14" /> 返回修改</router-link>
      <div class="mini-brand"><AppIcon name="compass" :size="14" /> 漫游 · 智能旅行助手</div>
    </div>

    <main class="plan-main">
      <section class="plan-visual">
        <div class="radar">
          <div class="radar-ring ring-1"></div>
          <div class="radar-ring ring-2"></div>
          <div class="radar-ring ring-3"></div>
          <div class="radar-sweep"></div>
          <div class="radar-core">
            <AppIcon name="sparkles" :size="26" />
          </div>
          <div class="radar-pin pin-1"><AppIcon name="pin" :size="12" /></div>
          <div class="radar-pin pin-2"><AppIcon name="meal" :size="12" /></div>
          <div class="radar-pin pin-3"><AppIcon name="hotel" :size="12" /></div>
        </div>
        <div class="visual-caption">
          <span class="pulse-dot"></span>
          {{ message }}
        </div>
      </section>

      <section class="plan-panel">
        <div class="eyebrow">GENERATING YOUR TRIP</div>
        <h1 v-if="!error">正在为你编排<br /><span>{{ planMeta.city || '这趟' }}旅行</span></h1>
        <h1 v-else>这次没有排成功</h1>

        <div v-if="planMeta.startDate" class="trip-brief">
          <span>{{ planMeta.city }}</span>
          <i></i>
          <span>{{ planMeta.startDate }} — {{ planMeta.endDate }}</span>
          <i></i>
          <span>{{ planMeta.adults }} 成人<span v-if="planMeta.children"> · {{ planMeta.children }} 儿童</span></span>
        </div>

        <div v-if="!error" class="progress-block">
          <div class="progress-head">
            <span>规划进度</span>
            <b>{{ progress }}%</b>
          </div>
          <div class="progress-track"><div class="progress-fill" :style="{ width: progress + '%' }"></div></div>
        </div>

        <div v-if="!error" class="stage-list">
          <div
            v-for="(item, index) in stages"
            :key="item.key"
            class="stage-row"
            :class="{
              done: index < activeIndex || finished,
              active: index === activeIndex && !finished,
            }"
          >
            <span class="stage-dot">
              <AppIcon v-if="index < activeIndex || finished" name="check" :size="11" />
              <span v-else>{{ index + 1 }}</span>
            </span>
            <div>
              <b>{{ item.label }}</b>
              <small>{{ item.desc }}</small>
            </div>
            <span v-if="index === activeIndex && !finished" class="stage-loading"><i></i><i></i><i></i></span>
          </div>
        </div>

        <div v-if="dayPreview.length && !finished" class="day-preview">
          <div v-for="day in dayPreview" :key="day.dayIndex" class="day-pill">
            <span>DAY {{ day.dayIndex }}</span>
            <b>{{ day.theme }}</b>
            <small>{{ day.count }} 个安排</small>
          </div>
        </div>

        <div v-if="error" class="error-box">
          <div class="error-icon"><AppIcon name="info" :size="18" /></div>
          <div>
            <b>生成失败</b>
            <p>{{ error }}</p>
            <p v-if="!error.includes('成都') && !error.includes('高德')" class="error-hint">
              请检查后端是否启动，或返回修改目的地后重试。
            </p>
          </div>
        </div>

        <div v-if="error" class="error-actions">
          <router-link to="/" class="btn btn-primary">返回修改需求</router-link>
          <button class="btn btn-ghost" @click="start">重试</button>
        </div>

        <p v-if="!error" class="plan-foot">
          <AppIcon name="info" :size="12" />
          规划过程会持续 20–60 秒，请保持页面打开。价格与营业时间以官方为准。
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.plan-page {
  background:
    radial-gradient(circle at 18% 18%, rgba(0, 113, 227, 0.2), transparent 32%),
    radial-gradient(circle at 82% 76%, rgba(0, 166, 160, 0.14), transparent 36%),
    #000;
  color: #f5f5f7;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}

.plan-page::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(circle at center, #000 12%, transparent 68%);
  pointer-events: none;
}

.plan-top {
  position: relative;
  z-index: 2;
  width: min(1180px, calc(100% - 44px));
  margin: 0 auto;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.back-link,
.mini-brand {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #a1a1a6;
  font-size: 11px;
}

.back-link:hover {
  color: #fff;
}

.mini-brand {
  letter-spacing: 0.01em;
}

.plan-main {
  position: relative;
  z-index: 2;
  width: min(1180px, calc(100% - 44px));
  margin: 0 auto;
  min-height: calc(100vh - 56px);
  display: grid;
  grid-template-columns: 0.9fr 1.1fr;
  gap: 76px;
  align-items: center;
  padding-bottom: 60px;
}

.plan-visual {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 25px;
}

.radar {
  width: min(390px, 68vw);
  aspect-ratio: 1;
  position: relative;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0, 113, 227, 0.12), transparent 68%);
}

.radar-ring {
  position: absolute;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  inset: 0;
}

.ring-1 { inset: 12%; }
.ring-2 { inset: 27%; }
.ring-3 { inset: 42%; }

.radar-sweep {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(from 0deg, transparent 0 78%, rgba(0, 166, 160, 0.22) 97%, transparent 100%);
  animation: rotate 5s linear infinite;
}

@keyframes rotate {
  to { transform: rotate(360deg); }
}

.radar-core {
  position: absolute;
  inset: 41%;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #5eead4;
  background: rgba(0, 0, 0, 0.72);
  border: 1px solid rgba(94, 234, 212, 0.24);
  box-shadow: 0 0 50px rgba(94, 234, 212, 0.08);
}

.radar-pin {
  position: absolute;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #93c5fd;
}

.pin-1 { top: 16%; left: 62%; }
.pin-2 { top: 60%; left: 12%; color: #5eead4; }
.pin-3 { top: 72%; left: 70%; color: #fdba74; }

.visual-caption {
  color: #a1a1a6;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 390px;
  text-align: center;
  line-height: 1.6;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #5eead4;
  box-shadow: 0 0 0 4px rgba(94, 234, 212, 0.1);
  animation: pulse 1.8s ease infinite;
}

@keyframes pulse {
  50% { box-shadow: 0 0 0 9px rgba(94, 234, 212, 0.02); }
}

.plan-panel {
  max-width: 540px;
}

.plan-panel .eyebrow {
  color: #6e6e73;
  font-size: 10px;
}

.plan-panel h1 {
  margin: 16px 0 22px;
  font-size: clamp(42px, 5.4vw, 70px);
  line-height: 1.03;
  letter-spacing: -0.055em;
  font-weight: 600;
}

.plan-panel h1 span {
  color: #5eead4;
}

.trip-brief {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  color: #a1a1a6;
  font-size: 12px;
}

.trip-brief i {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #6e6e73;
}

.progress-block {
  margin-top: 30px;
}

.progress-head {
  display: flex;
  justify-content: space-between;
  color: #a1a1a6;
  font-size: 10px;
  margin-bottom: 8px;
}

.progress-head b {
  color: #5eead4;
  font-size: 13px;
  font-weight: 500;
}

.progress-track {
  height: 4px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.12);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #0071e3, #5eead4);
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

.stage-list {
  margin-top: 25px;
  display: flex;
  flex-direction: column;
}

.stage-row {
  display: grid;
  grid-template-columns: 26px 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 11px 0;
  color: #6e6e73;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.stage-row.active {
  color: #f5f5f7;
}

.stage-row.done {
  color: #a1a1a6;
}

.stage-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.15);
  font-size: 9px;
  color: #6e6e73;
}

.stage-row.active .stage-dot {
  border-color: rgba(94, 234, 212, 0.4);
  color: #5eead4;
}

.stage-row.done .stage-dot {
  border-color: rgba(94, 234, 212, 0.24);
  background: rgba(94, 234, 212, 0.1);
  color: #2dd4bf;
}

.stage-row b {
  display: block;
  font-size: 12px;
  font-weight: 500;
}

.stage-row small {
  display: block;
  color: #6e6e73;
  font-size: 9px;
  margin-top: 2px;
}

.stage-loading {
  display: flex;
  gap: 3px;
}

.stage-loading i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #5eead4;
  animation: blink 1.2s infinite;
}

.stage-loading i:nth-child(2) { animation-delay: 0.15s; }
.stage-loading i:nth-child(3) { animation-delay: 0.3s; }

@keyframes blink {
  0%, 80%, 100% { opacity: 0.18; }
  40% { opacity: 1; }
}

.day-preview {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.day-pill {
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.035);
  border-radius: 12px;
  padding: 9px 11px;
  min-width: 108px;
}

.day-pill span {
  display: block;
  color: #5eead4;
  font-size: 8px;
  letter-spacing: 0.12em;
}

.day-pill b {
  display: block;
  color: #d1d1d6;
  font-size: 10px;
  margin-top: 2px;
  font-weight: 500;
}

.day-pill small {
  display: block;
  color: #6e6e73;
  font-size: 8.5px;
  margin-top: 2px;
}

.error-box {
  margin-top: 26px;
  display: flex;
  gap: 12px;
  border: 1px solid rgba(255, 99, 99, 0.2);
  background: rgba(215, 0, 21, 0.13);
  border-radius: 16px;
  padding: 16px;
}

.error-icon {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255, 99, 99, 0.12);
  color: #ff8a8a;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.error-box b {
  font-size: 12px;
}

.error-box p {
  margin: 5px 0 0;
  color: #ffb3b3;
  font-size: 10.5px;
  line-height: 1.7;
}

.error-box .error-hint {
  color: #a1a1a6;
}

.error-actions {
  display: flex;
  gap: 9px;
  margin-top: 17px;
}

.error-actions .btn-primary {
  background: #fff;
  color: #000;
}

.error-actions .btn-ghost {
  background: transparent;
  color: #d1d1d6;
  border-color: rgba(255, 255, 255, 0.18);
}

.plan-foot {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  color: #6e6e73;
  font-size: 9.5px;
  line-height: 1.6;
  margin-top: 26px;
}

@media (max-width: 940px) {
  .plan-main {
    grid-template-columns: 1fr;
    gap: 34px;
    padding-top: 30px;
  }

  .plan-visual {
    order: 2;
  }

  .radar {
    width: min(300px, 62vw);
  }

  .plan-panel {
    max-width: none;
  }
}

@media (max-width: 620px) {
  .plan-top,
  .plan-main {
    width: calc(100% - 28px);
  }

  .mini-brand {
    display: none;
  }

  .plan-panel h1 {
    font-size: 38px;
  }
}
</style>
