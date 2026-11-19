<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import BudgetPanel from '../components/BudgetPanel.vue'
import ExportModal from '../components/ExportModal.vue'
import MapCanvas from '../components/MapCanvas.vue'
import PoiSearchModal from '../components/PoiSearchModal.vue'
import { useSessionStore, useTripStore } from '../stores'
import type { Poi, RouteLeg, TripItem } from '../types'

const route = useRoute()
const router = useRouter()
const store = useTripStore()
const session = useSessionStore()
const showSearch = ref(false)
const showExport = ref(false)
const dragId = ref('')
const error = ref('')

const trip = computed(() => store.trip)
const day = computed(() => store.currentDay)
const dayRoutes = computed(() => store.dayRoutes)
const tripId = computed(() => String(route.params.tripId || ''))

const totalDays = computed(() => trip.value?.days.length || 0)
const itemCount = computed(() => day.value?.items.length || 0)

const typeMeta: Record<string, { label: string; icon: string; color: string }> = {
  attraction: { label: '景点', icon: 'attraction', color: '#2563eb' },
  meal: { label: '餐饮', icon: 'meal', color: '#c2410c' },
  hotel: { label: '住宿', icon: 'hotel', color: '#0f766e' },
  transit: { label: '交通', icon: 'route', color: '#7c3aed' },
}

const colors = ['#2563eb', '#f97316', '#0f766e', '#7c3aed', '#db2777', '#0891b2', '#ca8a04']

function fmt(cents: number) {
  return (cents / 100).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function typeLabel(item: TripItem) {
  return typeMeta[item.type]?.label || '安排'
}

function typeIcon(item: TripItem) {
  return typeMeta[item.type]?.icon || 'pin'
}

function dayColor(index: number) {
  return colors[(index - 1) % colors.length]
}

function routeBetween(index: number): RouteLeg | undefined {
  const items = day.value?.items || []
  const from = items[index]
  const to = items[index + 1]
  if (!from || !to) return undefined
  return dayRoutes.value.find((r) => r.fromItemId === from.id && r.toItemId === to.id)
}

function legLabel(route?: RouteLeg) {
  if (!route) return ''
  const mode = { walking: '步行', transit: '公交 / 地铁', driving: '打车' }[route.mode] || '移动'
  return `${mode} ${route.durationMin} 分钟${route.distanceM ? ` · ${route.distanceM >= 1000 ? (route.distanceM / 1000).toFixed(1) + ' km' : route.distanceM + ' m'}` : ''}`
}

function costLabel(item: TripItem) {
  if (!item.cost?.amountCents) return '免费'
  return `¥${fmt(item.cost.amountCents)}${item.cost.basis === 'room_night' ? '/间夜' : ''}`
}

function formatDate(date: string) {
  const d = new Date(date + 'T00:00:00')
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

async function load() {
  error.value = ''
  if (!tripId.value) {
    error.value = '缺少行程 ID'
    return
  }
  try {
    await store.load(tripId.value)
    if (trip.value?.days?.length) {
      store.selectedDay = trip.value.days[0].dayIndex
    }
  } catch (e: any) {
    error.value = e.message || '行程加载失败'
  }
}

onMounted(async () => {
  await session.ensure()
  await load()
})

watch(
  () => route.params.tripId,
  () => load(),
)

watch(
  () => store.selectedItemId,
  async (id) => {
    if (!id) return
    await nextTick()
    document.querySelector(`[data-item-id="${id}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  },
)

function startDrag(id: string) {
  dragId.value = id
}

function dropOn(targetId: string) {
  if (!day.value || !dragId.value || dragId.value === targetId) return
  const ids = day.value.items.map((i) => i.id)
  const from = ids.indexOf(dragId.value)
  const to = ids.indexOf(targetId)
  if (from < 0 || to < 0) return
  ids.splice(from, 1)
  ids.splice(to, 0, dragId.value)
  dragId.value = ''
  store.reorder(day.value.dayIndex, ids)
}

function move(itemId: string, delta: number) {
  if (!day.value) return
  const ids = day.value.items.map((i) => i.id)
  const index = ids.indexOf(itemId)
  const next = index + delta
  if (index < 0 || next < 0 || next >= ids.length) return
  ids.splice(index, 1)
  ids.splice(next, 0, itemId)
  store.reorder(day.value.dayIndex, ids)
}

async function remove(item: TripItem) {
  if (!window.confirm(`从行程中删除「${item.title}」？`)) return
  await store.removeItem(item.id)
}

function onAdd(poi: Poi) {
  if (!day.value) return
  showSearch.value = false
  store.addItem(day.value.dayIndex, poi)
}

function selectItem(id: string) {
  store.selectItem(id)
}
</script>

<template>
  <div class="trip-page">
    <header class="trip-header">
      <div class="trip-header-inner">
        <router-link to="/" class="brand">
          <span class="brand-mark"><AppIcon name="compass" :size="18" /></span>
          <span class="brand-text"><strong>漫游</strong><small>SMART TRAVEL</small></span>
        </router-link>
        <span class="header-sep"></span>
        <div v-if="trip" class="header-title">
          <b>{{ trip.title }}</b>
          <span>{{ trip.startDate }} — {{ trip.endDate }} · {{ trip.days.length }} 天 · {{ trip.meta.travelers.adults + trip.meta.travelers.children }} 人</span>
        </div>
        <div v-else class="header-title"><b>行程工作台</b><span>正在加载…</span></div>
        <div class="header-actions">
          <span v-if="trip?.meta.demo" class="demo-chip"><span></span>演示模式</span>
          <router-link to="/" class="btn btn-ghost header-back"><AppIcon name="refresh" :size="13" /> 重新规划</router-link>
          <button class="btn btn-primary" type="button" @click="showExport = true">
            <AppIcon name="download" :size="14" /> 导出
          </button>
        </div>
      </div>
    </header>

    <div v-if="store.loading && !trip" class="loading-screen">
      <span class="loading-ring"></span>
      <p>正在加载行程…</p>
    </div>

    <div v-else-if="error" class="error-screen">
      <div class="error-card">
        <div class="error-icon"><AppIcon name="info" :size="22" /></div>
        <h2>没有找到这段行程</h2>
        <p>{{ error }}</p>
        <router-link to="/" class="btn btn-primary">去规划一段新的</router-link>
      </div>
    </div>

    <main v-else-if="trip && day" class="trip-main">
      <section class="timeline-panel">
        <div class="panel-top">
          <div>
            <div class="eyebrow">ITINERARY</div>
            <h1>每日行程</h1>
          </div>
          <span class="item-count">{{ totalDays }} 天 · {{ trip.days.reduce((n, d) => n + d.items.length, 0) }} 个安排</span>
        </div>

        <div class="day-tabs">
          <button
            v-for="d in trip.days"
            :key="d.dayIndex"
            type="button"
            class="day-tab"
            :class="{ active: d.dayIndex === store.selectedDay }"
            :style="{ '--day-color': dayColor(d.dayIndex) }"
            @click="store.selectDay(d.dayIndex)"
          >
            <span class="tab-dot"></span>
            <b>DAY {{ d.dayIndex }}</b>
            <small>{{ formatDate(d.date) }}</small>
          </button>
        </div>

        <div class="day-heading">
          <div class="day-heading-top">
            <h2>{{ day.theme }}</h2>
            <span class="day-date">{{ day.date }} · 第 {{ day.dayIndex }} 天</span>
          </div>
          <p>{{ day.summary }}</p>
          <div class="day-stats">
            <span><AppIcon name="attraction" :size="12" /> {{ day.items.filter((i) => i.type === 'attraction').length }} 景点</span>
            <span><AppIcon name="meal" :size="12" /> {{ day.items.filter((i) => i.type === 'meal').length }} 餐</span>
            <span v-if="day.items.some((i) => i.type === 'hotel')"><AppIcon name="hotel" :size="12" /> 住宿</span>
            <button type="button" class="add-inline" @click="showSearch = true"><AppIcon name="plus" :size="12" /> 添加安排</button>
          </div>
        </div>

        <div class="timeline">
          <template v-for="(item, index) in day.items" :key="item.id">
            <article
              class="item-card"
              :class="{
                selected: store.selectedItemId === item.id,
                dragging: dragId === item.id,
              }"
              :style="{ '--item-color': typeMeta[item.type]?.color || '#2563eb' }"
              :data-item-id="item.id"
              draggable="true"
              @dragstart="startDrag(item.id)"
              @dragover.prevent
              @drop.prevent="dropOn(item.id)"
              @dragend="dragId = ''"
              @click="selectItem(item.id)"
            >
              <div class="drag-handle" title="拖拽排序"><AppIcon name="menu" :size="12" /></div>
              <div class="item-time">
                <b>{{ item.startTime }}</b>
                <span>{{ item.endTime }}</span>
              </div>
              <div class="item-divider">
                <span class="item-dot"></span>
              </div>
              <div class="item-body">
                <div class="item-top">
                  <div class="item-title-row">
                    <span class="type-pill" :style="{ color: typeMeta[item.type]?.color, background: typeMeta[item.type]?.color + '12' }">
                      <AppIcon :name="typeIcon(item)" :size="11" />
                      {{ typeLabel(item) }}
                    </span>
                    <h3>{{ item.title }}</h3>
                  </div>
                  <div class="item-actions" @click.stop>
                    <button type="button" :title="item.locked ? '取消锁定' : '锁定，不被重新优化'" @click="store.toggleLock(item.id, !item.locked)">
                      <AppIcon :name="item.locked ? 'lock' : 'unlock'" :size="12" />
                    </button>
                    <button type="button" title="上移" :disabled="index === 0" @click="move(item.id, -1)">
                      <AppIcon name="arrow-up" :size="12" />
                    </button>
                    <button type="button" title="下移" :disabled="index === day.items.length - 1" @click="move(item.id, 1)">
                      <AppIcon name="arrow-down" :size="12" />
                    </button>
                    <button type="button" class="delete" title="删除" @click="remove(item)">
                      <AppIcon name="trash" :size="12" />
                    </button>
                  </div>
                </div>

                <div class="item-meta">
                  <span class="addr"><AppIcon name="pin" :size="11" /> {{ item.address || '地址以高德为准' }}</span>
                  <span v-if="item.rating" class="rating">★ {{ item.rating.toFixed(1) }}</span>
                </div>

                <p v-if="item.description" class="item-desc">{{ item.description }}</p>

                <div class="item-bottom">
                  <span class="cost">{{ costLabel(item) }} <em v-if="item.cost.amountCents">参考价</em></span>
                  <span class="duration"><AppIcon name="clock" :size="10" /> {{ item.durationMin }} 分钟</span>
                  <a v-if="item.bookingUrl" :href="item.bookingUrl" target="_blank" rel="noreferrer" class="booking" @click.stop>
                    查看详情 <AppIcon name="external" :size="9" />
                  </a>
                </div>

                <p v-if="item.notes" class="item-note">{{ item.notes }}</p>
              </div>
            </article>

            <div v-if="index < day.items.length - 1" class="leg-row">
              <span class="leg-line"></span>
              <span class="leg-text"><AppIcon name="route" :size="10" /> {{ legLabel(routeBetween(index)) || '路程待确认' }}</span>
            </div>
          </template>

          <div v-if="!day.items.length" class="empty-day">
            <div class="empty-icon"><AppIcon name="compass" :size="24" /></div>
            <b>这一天还是空的</b>
            <p>添加一个景点或餐厅，路线与预算会自动重算。</p>
            <button class="btn btn-teal" type="button" @click="showSearch = true"><AppIcon name="plus" :size="13" /> 添加安排</button>
          </div>
        </div>

        <button class="add-day-btn" type="button" @click="showSearch = true">
          <AppIcon name="plus" :size="14" /> 添加景点 / 餐厅 / 酒店
        </button>
      </section>

      <section class="map-panel">
        <MapCanvas
          :trip="trip"
          :selected-day="store.selectedDay"
          :selected-item-id="store.selectedItemId"
          @select-item="store.selectItem"
        />
      </section>

      <section class="budget-wrap">
        <BudgetPanel
          :budget="trip.budget"
          :day-count="trip.days.length"
          :selected-day="store.selectedDay"
          @select-day="store.selectDay"
        />
      </section>
    </main>

    <PoiSearchModal
      v-if="day"
      :open="showSearch"
      :city="trip?.destination.city || ''"
      :day-index="day.dayIndex"
      :day-theme="day.theme"
      @close="showSearch = false"
      @add="onAdd"
    />

    <ExportModal
      v-if="trip"
      :open="showExport"
      :trip-id="trip.id"
      :title="trip.title"
      @close="showExport = false"
    />

    <div v-if="store.toast.visible" class="global-toast" :class="store.toast.kind">
      {{ store.toast.message }}
    </div>

    <div v-if="store.saving" class="saving-hint"><span class="loading-ring"></span> 正在重算路线与预算…</div>
  </div>
</template>

<style scoped>
.trip-page {
  min-height: 100vh;
  background: var(--bg-soft);
}

.trip-header {
  position: sticky;
  top: 0;
  z-index: 30;
  background: rgba(251, 251, 253, 0.82);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
}

.trip-header-inner {
  width: calc(100% - 36px);
  max-width: 1700px;
  margin: 0 auto;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-shrink: 0;
  color: var(--ink);
}

.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  background: var(--ink);
  color: #fff;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1;
}

.brand-text strong {
  font-size: 15px;
  letter-spacing: -0.02em;
}

.brand-text small {
  color: var(--faint);
  font-size: 6px;
  letter-spacing: 0.14em;
  margin-top: 4px;
}

.header-sep {
  width: 1px;
  height: 22px;
  background: var(--line);
  margin: 0 3px;
}

.header-title {
  min-width: 0;
  flex: 1;
}

.header-title b {
  display: block;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-title span {
  display: block;
  color: var(--faint);
  font-size: 9.5px;
  margin-top: 2px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.demo-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 99px;
  background: var(--bg-soft);
  color: var(--faint);
  padding: 5px 9px;
  font-size: 8.5px;
  font-weight: 500;
}

.demo-chip span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #ff9f0a;
}

.header-back {
  font-size: 10px;
  padding: 7px 10px;
  border-color: transparent;
  background: transparent;
  color: var(--muted);
}

.header-back:hover {
  background: var(--bg-soft);
  border-color: transparent;
}

.header-actions > .btn-primary {
  padding: 8px 13px;
  font-size: 10px;
}

.trip-main {
  width: calc(100% - 32px);
  max-width: 1700px;
  margin: 0 auto;
  padding: 16px 0 20px;
  display: grid;
  grid-template-columns: 402px minmax(0, 1fr) 305px;
  gap: 16px;
  height: calc(100vh - 56px);
  align-items: stretch;
}

.timeline-panel,
.map-panel,
.budget-wrap {
  min-height: 0;
}

.timeline-panel {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.panel-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 21px 22px 12px;
}

.panel-top h1 {
  margin: 6px 0 0;
  font-size: 24px;
  line-height: 1.1;
  letter-spacing: -0.045em;
  font-weight: 600;
}

.panel-top .eyebrow {
  font-size: 9px;
}

.item-count {
  color: var(--faint);
  font-size: 10px;
  padding-top: 11px;
}

.day-tabs {
  display: flex;
  gap: 3px;
  overflow-x: auto;
  margin: 0 16px 4px;
  padding: 4px;
  background: var(--bg-soft);
  border-radius: 13px;
  scrollbar-width: none;
}

.day-tabs::-webkit-scrollbar {
  display: none;
}

.day-tab {
  border: 0;
  background: transparent;
  border-radius: 10px;
  padding: 8px 11px;
  color: var(--muted);
  min-width: 68px;
  text-align: left;
  flex-shrink: 0;
  transition: 0.2s ease;
}

.day-tab b {
  display: block;
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.day-tab small {
  display: block;
  font-size: 9px;
  margin-top: 2px;
  color: var(--faint);
}

.day-tab .tab-dot {
  display: block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--day-color);
  margin-bottom: 5px;
  opacity: 0.55;
}

.day-tab.active {
  background: #fff;
  color: var(--ink);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.day-tab.active .tab-dot {
  opacity: 1;
}

.day-heading {
  padding: 17px 22px 13px;
}

.day-heading-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.day-heading h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.15;
  letter-spacing: -0.04em;
  font-weight: 600;
}

.day-date {
  color: var(--faint);
  font-size: 9px;
  white-space: nowrap;
}

.day-heading > p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.6;
}

.day-stats {
  display: flex;
  align-items: center;
  gap: 13px;
  margin-top: 12px;
  color: var(--faint);
  font-size: 9.5px;
}

.day-stats > span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.add-inline {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: var(--blue);
  padding: 3px 0;
  font-size: 10px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.add-inline:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.timeline {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 10px 18px;
}

.item-card {
  position: relative;
  display: flex;
  gap: 7px;
  border: 1px solid transparent;
  border-radius: 16px;
  background: var(--bg-soft);
  padding: 12px 10px 12px 4px;
  cursor: pointer;
  transition: 0.2s ease;
}

.item-card:hover {
  background: #f0f0f2;
}

.item-card.selected {
  background: #fff;
  border-color: rgba(0, 113, 227, 0.55);
  box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.08);
}

.item-card.dragging {
  opacity: 0.45;
}

.drag-handle {
  width: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c7c7cc;
  cursor: grab;
  flex-shrink: 0;
}

.item-time {
  width: 43px;
  padding-top: 2px;
  text-align: right;
  flex-shrink: 0;
}

.item-time b {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}

.item-time span {
  display: block;
  font-size: 8.5px;
  color: var(--faint);
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.item-divider {
  width: 9px;
  display: flex;
  justify-content: center;
  position: relative;
  flex-shrink: 0;
}

.item-divider::before {
  content: "";
  position: absolute;
  top: -15px;
  bottom: -15px;
  width: 1px;
  background: #e5e5ea;
}

.item-dot {
  position: relative;
  z-index: 1;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--item-color);
  margin-top: 5px;
  border: 2px solid var(--bg-soft);
  box-shadow: 0 0 0 1px var(--item-color);
}

.item-card.selected .item-dot {
  border-color: #fff;
}

.item-body {
  flex: 1;
  min-width: 0;
}

.item-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 5px;
}

.item-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-wrap: wrap;
}

.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border-radius: 99px;
  padding: 2px 6px;
  font-size: 7.5px;
  font-weight: 600;
  flex-shrink: 0;
}

.item-title-row h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-actions {
  display: flex;
  gap: 1px;
  flex-shrink: 0;
  opacity: 0;
  transition: 0.16s ease;
}

.item-card:hover .item-actions,
.item-card.selected .item-actions {
  opacity: 1;
}

.item-actions button {
  width: 22px;
  height: 22px;
  border: 0;
  background: transparent;
  color: var(--faint);
  border-radius: 6px;
  display: grid;
  place-items: center;
  padding: 0;
}

.item-actions button:hover {
  background: #fff;
  color: var(--ink);
}

.item-actions button.delete:hover {
  background: #fff2f3;
  color: var(--rose);
}

.item-actions button:disabled {
  opacity: 0.25;
  cursor: default;
}

.item-meta {
  display: flex;
  gap: 7px;
  align-items: center;
  margin-top: 5px;
  color: var(--faint);
  font-size: 9.5px;
}

.addr {
  display: flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rating {
  color: #bf4800;
  flex-shrink: 0;
}

.item-desc {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-bottom {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 6px;
  color: var(--faint);
  font-size: 9px;
}

.cost {
  color: #bf4800;
  font-weight: 500;
}

.cost em {
  font-style: normal;
  color: #c7a17f;
  font-weight: 400;
  font-size: 7px;
  margin-left: 2px;
}

.duration {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.booking {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--blue);
  font-size: 8.5px;
}

.item-note {
  margin: 6px 0 0;
  color: var(--teal);
  background: rgba(0, 143, 140, 0.07);
  border-radius: 6px;
  padding: 4px 6px;
  font-size: 8px;
  line-height: 1.5;
}

.leg-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 3px 0 3px 66px;
  color: var(--faint);
  font-size: 8px;
}

.leg-line {
  width: 1px;
  height: 15px;
  background: #e5e5ea;
  margin-left: 4px;
}

.leg-text {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: var(--bg-soft);
  border-radius: 99px;
  padding: 2px 6px;
}

.empty-day {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 38px 16px;
  color: var(--faint);
}

.empty-icon {
  width: 50px;
  height: 50px;
  border-radius: 15px;
  background: var(--bg-soft);
  display: grid;
  place-items: center;
  color: var(--faint);
  margin-bottom: 11px;
}

.empty-day b {
  font-size: 12px;
  color: var(--ink-2);
}

.empty-day p {
  margin: 5px 0 13px;
  font-size: 9.5px;
  line-height: 1.6;
  max-width: 220px;
}

.empty-day .btn {
  font-size: 10px;
  padding: 8px 11px;
}

.add-day-btn {
  margin: 0 16px 14px;
  border: 1px dashed #d2d2d7;
  background: transparent;
  color: var(--muted);
  border-radius: 12px;
  padding: 10px;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition: 0.2s ease;
}

.add-day-btn:hover {
  border-color: var(--blue);
  color: var(--blue);
  background: rgba(0, 113, 227, 0.04);
}

.map-panel {
  min-height: 300px;
}

.budget-wrap {
  min-height: 0;
  overflow: hidden;
}

.loading-screen,
.error-screen {
  min-height: calc(100vh - 56px);
  display: grid;
  place-items: center;
  color: var(--faint);
  gap: 10px;
}

.loading-screen p {
  font-size: 11px;
}

.loading-ring {
  width: 24px;
  height: 24px;
  border: 2px solid #e5e5ea;
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}

.error-card {
  background: #fff;
  border-radius: 22px;
  padding: 32px;
  text-align: center;
  max-width: 380px;
  box-shadow: var(--shadow-sm);
}

.error-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #fff2f3;
  color: var(--rose);
  display: grid;
  place-items: center;
  margin: 0 auto 13px;
}

.error-card h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.error-card p {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.7;
  margin: 8px 0 17px;
}

.saving-hint {
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 60;
  display: flex;
  align-items: center;
  gap: 7px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
  border-radius: 99px;
  padding: 9px 13px;
  color: var(--muted);
  font-size: 9.5px;
  backdrop-filter: blur(12px);
}

.saving-hint .loading-ring {
  width: 14px;
  height: 14px;
  border-width: 1.5px;
}

@media (max-width: 1280px) {
  .trip-main {
    grid-template-columns: 380px minmax(0, 1fr) 285px;
  }
}

@media (max-width: 1080px) {
  .trip-main {
    grid-template-columns: 360px minmax(0, 1fr);
    height: auto;
    min-height: calc(100vh - 56px);
  }

  .budget-wrap {
    grid-column: 1 / -1;
  }

  .map-panel {
    min-height: 520px;
  }
}

@media (max-width: 820px) {
  .trip-header-inner {
    width: calc(100% - 20px);
    height: 52px;
    gap: 8px;
  }

  .brand-text,
  .header-sep,
  .header-back {
    display: none;
  }

  .header-title b {
    font-size: 11px;
  }

  .header-title span {
    font-size: 8px;
  }

  .demo-chip {
    display: none;
  }

  .trip-main {
    width: calc(100% - 20px);
    display: flex;
    flex-direction: column;
    height: auto;
    padding: 10px 0 20px;
  }

  .timeline-panel {
    max-height: none;
    overflow: visible;
  }

  .timeline {
    overflow: visible;
  }

  .map-panel {
    height: 440px;
    min-height: 440px;
  }

  .budget-wrap {
    overflow: visible;
  }

  .item-actions {
    opacity: 1;
  }
}
</style>
