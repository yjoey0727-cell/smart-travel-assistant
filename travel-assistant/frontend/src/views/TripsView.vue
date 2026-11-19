<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import AppIcon from '../components/AppIcon.vue'
import { api } from '../api'
import type { TripSummary } from '../types'

const router = useRouter()
const trips = ref<TripSummary[]>([])
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  try {
    trips.value = await api.listTrips()
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function remove(trip: TripSummary) {
  if (!window.confirm(`删除「${trip.title}」？`)) return
  try {
    await api.deleteTrip(trip.id)
    trips.value = trips.value.filter((t) => t.id !== trip.id)
  } catch (e: any) {
    error.value = e.message || '删除失败'
  }
}

function fmt(cents: number) {
  return (cents / 100).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function fmtDate(value: string) {
  const d = new Date(value + 'T00:00:00')
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

onMounted(load)
</script>

<template>
  <div class="page trips-page">
    <AppHeader />
    <main class="container">
      <div class="page-head">
        <div>
          <div class="eyebrow">YOUR TRIPS</div>
          <h1>每一次出发，<br />都在这里。</h1>
          <p>匿名会话期间生成的行程保存在这台设备上，无需登录。</p>
        </div>
        <router-link to="/" class="btn btn-primary"><AppIcon name="sparkles" :size="14" /> 规划新行程</router-link>
      </div>

      <div v-if="loading" class="loading-state">
        <span class="loading-ring"></span>
        正在加载…
      </div>

      <div v-else-if="error" class="empty-state">
        <AppIcon name="info" :size="26" />
        <p>{{ error }}</p>
        <button class="btn btn-ghost" @click="load">重试</button>
      </div>

      <div v-else-if="!trips.length" class="empty-state">
        <div class="empty-icon"><AppIcon name="compass" :size="30" /></div>
        <h2>还没有行程</h2>
        <p>从下一段旅行开始。输入任何国内城市，剩下的交给漫游。</p>
        <router-link to="/" class="btn btn-teal">开始第一段旅行 <AppIcon name="chevron-right" :size="14" /></router-link>
      </div>

      <div v-else class="trip-grid">
        <article v-for="trip in trips" :key="trip.id" class="trip-card">
          <div class="trip-cover">
            <div class="cover-shade"></div>
            <span class="cover-city">{{ trip.city }}</span>
            <span class="cover-days">{{ trip.days }} DAYS</span>
            <div class="cover-lines"></div>
          </div>
          <div class="trip-body">
            <div class="trip-top">
              <h2>{{ trip.title }}</h2>
              <span class="version">v{{ trip.version }}</span>
            </div>
            <p class="trip-date">{{ trip.startDate }} — {{ trip.endDate }} · {{ trip.days }} 天</p>
            <div class="trip-bottom">
              <div class="trip-price"><span>参考预算</span><b>¥{{ fmt(trip.totalCents) }}</b></div>
              <div class="trip-actions">
                <button type="button" class="icon-btn" title="删除" @click="remove(trip)"><AppIcon name="trash" :size="13" /></button>
                <button type="button" class="btn btn-primary" @click="router.push(`/trips/${trip.id}`)">打开 <AppIcon name="chevron-right" :size="13" /></button>
              </div>
            </div>
          </div>
        </article>
      </div>

      <footer class="trips-footer">漫游 · 智能旅行助手 · 行程价格均为参考估算</footer>
    </main>
  </div>
</template>

<style scoped>
.trips-page {
  background: var(--bg-soft);
  min-height: 100vh;
}

.container {
  padding: 64px 0 40px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  margin-bottom: 34px;
}

.page-head h1 {
  margin: 10px 0 0;
  font-size: clamp(38px, 4.6vw, 56px);
  line-height: 1.05;
  letter-spacing: -0.055em;
  font-weight: 600;
}

.page-head p {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 13px;
}

.page-head .btn {
  padding: 12px 20px;
  font-size: 13px;
}

.loading-state,
.empty-state {
  min-height: 380px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--faint);
  font-size: 12px;
  background: rgba(255, 255, 255, 0.64);
  border-radius: 28px;
}

.loading-ring {
  width: 24px;
  height: 24px;
  border: 2px solid #e5e5ea;
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #fff;
  display: grid;
  place-items: center;
  color: var(--blue);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.05);
}

.empty-state h2 {
  margin: 2px 0 0;
  font-size: 24px;
  letter-spacing: -0.035em;
  color: var(--ink);
}

.empty-state p {
  margin: 0;
  font-size: 12px;
  max-width: 380px;
  text-align: center;
  line-height: 1.7;
}

.trip-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.trip-card {
  background: #fff;
  border-radius: 25px;
  overflow: hidden;
  transition: transform 0.32s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.32s ease;
}

.trip-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 22px 50px rgba(0, 0, 0, 0.11);
}

.trip-cover {
  height: 172px;
  position: relative;
  overflow: hidden;
  background: linear-gradient(145deg, #0b2b3a 0%, #123c62 48%, #0d5c63 100%);
}

.cover-shade {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 82% 12%, rgba(94, 234, 212, 0.24), transparent 38%);
}

.cover-city {
  position: absolute;
  left: 22px;
  bottom: 22px;
  color: #fff;
  font-size: 37px;
  font-weight: 600;
  letter-spacing: -0.05em;
  z-index: 1;
}

.cover-days {
  position: absolute;
  right: 20px;
  top: 18px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 9px;
  letter-spacing: 0.14em;
  z-index: 1;
}

.cover-lines {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(110deg, #000, transparent 88%);
}

.trip-body {
  padding: 20px 21px 21px;
}

.trip-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.trip-top h2 {
  margin: 0;
  font-size: 18px;
  line-height: 1.35;
  letter-spacing: -0.03em;
  font-weight: 600;
}

.version {
  color: var(--faint);
  font-size: 8px;
  border-radius: 99px;
  background: var(--bg-soft);
  padding: 3px 7px;
  flex-shrink: 0;
}

.trip-date {
  margin: 7px 0 20px;
  color: var(--faint);
  font-size: 10px;
}

.trip-bottom {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
}

.trip-price span {
  display: block;
  color: var(--faint);
  font-size: 8.5px;
}

.trip-price b {
  display: block;
  font-size: 26px;
  color: var(--ink);
  letter-spacing: -0.05em;
  margin-top: 2px;
  font-weight: 600;
}

.trip-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.trip-actions .btn {
  padding: 9px 14px;
  font-size: 10px;
}

.icon-btn {
  width: 32px;
  height: 32px;
  border: 0;
  background: var(--bg-soft);
  border-radius: 50%;
  color: var(--faint);
  display: grid;
  place-items: center;
}

.icon-btn:hover {
  background: #fff2f3;
  color: var(--rose);
}

.trips-footer {
  text-align: center;
  color: var(--faint);
  font-size: 9px;
  padding-top: 44px;
}

@media (max-width: 980px) {
  .trip-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 620px) {
  .container {
    padding-top: 42px;
  }

  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-head .btn {
    width: 100%;
  }

  .trip-grid {
    grid-template-columns: 1fr;
  }
}
</style>
