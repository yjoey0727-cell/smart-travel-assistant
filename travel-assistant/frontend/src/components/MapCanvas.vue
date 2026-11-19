<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { DayPlan, RouteLeg, Trip } from '../types'
import AppIcon from './AppIcon.vue'

const props = defineProps<{
  trip: Trip
  selectedDay: number
  selectedItemId?: string
}>()
const emit = defineEmits<{ (e: 'select-item', id: string): void }>()

const dayColors = ['#2563eb', '#f97316', '#0f766e', '#7c3aed', '#db2777', '#0891b2', '#ca8a04']
const mapEl = ref<HTMLDivElement | null>(null)
const mapReady = ref(false)
const mapFailed = ref(false)
const loading = ref(false)
const amapKey = import.meta.env.VITE_AMAP_KEY || ''
const securityCode = import.meta.env.VITE_AMAP_SECURITY_CODE || ''

let amap: any = null
let map: any = null
let overlays: any[] = []
let amapPromise: Promise<any> | null = null

const day = computed<DayPlan | undefined>(() =>
  props.trip.days.find((d) => d.dayIndex === props.selectedDay) || props.trip.days[0],
)
const items = computed(() => (day.value?.items || []).filter((i) => i.location?.lng && i.location?.lat))
const routes = computed<RouteLeg[]>(() =>
  (props.trip.routes || []).filter((r) => r.dayIndex === props.selectedDay),
)
const color = computed(() => dayColors[(props.selectedDay - 1) % dayColors.length])
const city = computed(() => props.trip.destination.city)

function shortTitle(title: string) {
  return title.length > 10 ? title.slice(0, 10) + '…' : title
}

const fallback = computed(() => {
  const list = items.value
  if (!list.length) return { markers: [], paths: [] as string[], viewBox: '0 0 820 560' }
  const lngs = list.map((i) => i.location.lng)
  const lats = list.map((i) => i.location.lat)
  const minLng = Math.min(...lngs)
  const maxLng = Math.max(...lngs)
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  const width = 820
  const height = 560
  const pad = 80
  const spanLng = Math.max(0.004, maxLng - minLng)
  const spanLat = Math.max(0.004, maxLat - minLat)
  const scale = Math.min((width - pad * 2) / spanLng, (height - pad * 2) / spanLat)
  const offsetX = (width - spanLng * scale) / 2
  const offsetY = (height - spanLat * scale) / 2
  const project = (lng: number, lat: number) => ({
    x: offsetX + (lng - minLng) * scale,
    y: height - offsetY - (lat - minLat) * scale,
  })
  const markers = list.map((item, index) => ({
    item,
    n: index + 1,
    ...project(item.location.lng, item.location.lat),
  }))
  const byId = new Map(markers.map((m) => [m.item.id, m]))
  const paths: string[] = []
  for (const route of routes.value) {
    let points = route.polyline || []
    if (!points.length) {
      const a = byId.get(route.fromItemId)
      const b = byId.get(route.toItemId)
      if (!a || !b) continue
      points = [
        [a.item.location.lng, a.item.location.lat],
        [b.item.location.lng, b.item.location.lat],
      ]
    }
    const coords = points
      .map((p) => {
        const pt = project(p[0], p[1])
        return `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`
      })
      .join(' ')
    if (coords) paths.push(coords)
  }
  if (!paths.length && markers.length > 1) {
    paths.push(markers.map((m) => `${m.x.toFixed(1)},${m.y.toFixed(1)}`).join(' '))
  }
  return { markers, paths, viewBox: `0 0 ${width} ${height}` }
})

function loadAmap(): Promise<any> {
  if (amapPromise) return amapPromise
  amapPromise = new Promise((resolve, reject) => {
    if (window.AMap) {
      resolve(window.AMap)
      return
    }
    if (!amapKey) {
      reject(new Error('no key'))
      return
    }
    if (securityCode) {
      window._AMapSecurityConfig = { securityJsCode: securityCode }
    }
    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(amapKey)}&plugin=AMap.Scale,AMap.ToolBar`
    script.async = true
    script.onload = () => (window.AMap ? resolve(window.AMap) : reject(new Error('AMap 未加载')))
    script.onerror = () => reject(new Error('高德地图脚本加载失败'))
    document.head.appendChild(script)
  })
  return amapPromise
}

async function initMap() {
  if (!amapKey || !mapEl.value) {
    mapFailed.value = true
    return
  }
  loading.value = true
  try {
    amap = await loadAmap()
    map = new amap.Map(mapEl.value, {
      zoom: 12,
      center: [props.trip.destination.center.lng, props.trip.destination.center.lat],
      viewMode: '2D',
      resizeEnable: true,
      mapStyle: 'amap://styles/whitesmoke',
    })
    map.addControl(new amap.Scale({ position: 'LB' }))
    map.addControl(new amap.ToolBar({ position: 'RB' }))
    mapReady.value = true
    await nextTick()
    renderMap(true)
  } catch {
    mapFailed.value = true
  } finally {
    loading.value = false
  }
}

function markerHtml(index: number, selected: boolean) {
  return `<div class="ta-marker${selected ? ' selected' : ''}" style="--marker-color:${color.value}">
    <span>${index}</span>
  </div>`
}

function renderMap(fit = true) {
  if (!map || !amap) return
  map.remove(overlays)
  overlays = []
  const markers: any[] = []
  items.value.forEach((item, index) => {
    const marker = new amap.Marker({
      position: [item.location.lng, item.location.lat],
      content: markerHtml(index + 1, item.id === props.selectedItemId),
      offset: new amap.Pixel(-15, -15),
      zIndex: 100 + index,
      title: item.title,
    })
    marker.on('click', () => emit('select-item', item.id))
    markers.push(marker)
  })
  const lines: any[] = []
  for (const route of routes.value) {
    if (!route.polyline || route.polyline.length < 2) continue
    lines.push(
      new amap.Polyline({
        path: route.polyline,
        strokeColor: color.value,
        strokeWeight: 5,
        strokeOpacity: 0.82,
        lineJoin: 'round',
        lineCap: 'round',
        showDir: true,
        zIndex: 20,
      }),
    )
  }
  overlays = [...lines, ...markers]
  map.add(overlays)
  if (fit && markers.length) {
    map.setFitView(markers, false, [70, 70, 70, 70], 14)
  }
  if (props.selectedItemId) {
    const item = items.value.find((i) => i.id === props.selectedItemId)
    if (item) map.setZoomAndCenter(14, [item.location.lng, item.location.lat])
  }
}

function resize() {
  map?.resize()
}

onMounted(() => {
  if (!amapKey) {
    mapFailed.value = true
    return
  }
  initMap()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  if (map) map.destroy()
  map = null
})

watch(
  () => [props.selectedDay, props.trip.version],
  () => {
    if (mapReady.value) renderMap(true)
  },
)
watch(
  () => props.selectedItemId,
  () => {
    if (mapReady.value) renderMap(false)
  },
)
</script>

<template>
  <div class="map-shell">
    <div ref="mapEl" class="real-map"></div>

    <div v-if="!mapReady" class="fallback-map">
      <div class="map-grid"></div>
      <svg :viewBox="fallback.viewBox" preserveAspectRatio="xMidYMid meet" class="map-svg">
        <defs>
          <linearGradient id="river" x1="0" x2="1">
            <stop offset="0%" stop-color="#dbeafe" />
            <stop offset="100%" stop-color="#e0f2fe" />
          </linearGradient>
        </defs>
        <path d="M0 400 C 160 350, 250 460, 400 410 S 670 330, 820 380" fill="none" stroke="url(#river)" stroke-width="26" stroke-linecap="round" opacity=".8" />
        <path d="M0 400 C 160 350, 250 460, 400 410 S 670 330, 820 380" fill="none" stroke="#bfdbfe" stroke-width="1" opacity=".7" />
        <polyline
          v-for="(path, index) in fallback.paths"
          :key="index"
          :points="path"
          fill="none"
          :stroke="color"
          stroke-width="3.4"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity=".72"
        />
        <g
          v-for="marker in fallback.markers"
          :key="marker.item.id"
          class="map-marker-group"
          :class="{ selected: marker.item.id === selectedItemId }"
          @click="emit('select-item', marker.item.id)"
        >
          <circle :cx="marker.x" :cy="marker.y" r="16" :fill="color" stroke="#fff" stroke-width="3" />
          <text :x="marker.x" :y="marker.y + 4.5" text-anchor="middle" fill="#fff" font-size="11" font-weight="700">{{ marker.n }}</text>
          <text
            v-if="marker.item.id === selectedItemId || fallback.markers.length <= 3"
            :x="marker.x + (marker.n % 2 === 0 ? -22 : 22)"
            :y="marker.y + 4"
            :text-anchor="marker.n % 2 === 0 ? 'end' : 'start'"
            fill="#334155"
            font-size="10"
            font-weight="500"
          >{{ shortTitle(marker.item.title) }}</text>
        </g>
      </svg>
      <div class="map-watermark">
        <span class="wm-pin"><AppIcon name="pin" :size="12" /></span>
        <span>{{ city }} · 路线示意</span>
        <span class="wm-sep"></span>
        <span>{{ mapFailed && amapKey ? '高德加载失败，已切换示意' : '配置 VITE_AMAP_KEY 显示真实地图' }}</span>
      </div>
      <div v-if="loading" class="map-loading">正在加载高德地图…</div>
    </div>

    <div class="map-topbar">
      <div class="map-city">
        <AppIcon name="pin" :size="13" />
        <b>{{ city }}</b>
        <span>DAY {{ selectedDay }}</span>
      </div>
      <div class="map-legend">
        <span class="legend-dot" :style="{ background: color }"></span>
        {{ day?.theme || '路线' }}
        <span class="legend-count">{{ items.length }} 个点</span>
      </div>
    </div>

    <div class="map-bottom">
      <span><AppIcon name="route" :size="12" /> {{ routes.length }} 段路线</span>
      <span v-if="routes.some((r) => r.status !== 'ok')" class="estimated">部分路线为估算</span>
      <span class="map-tip">点击标记查看对应行程</span>
    </div>
  </div>
</template>

<style>
.ta-marker {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--marker-color);
  border: 3px solid #fff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.28);
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.15s ease;
  font-family: var(--font);
}

.ta-marker:hover,
.ta-marker.selected {
  transform: scale(1.2);
}

.ta-marker.selected {
  box-shadow: 0 0 0 5px rgba(37, 99, 235, 0.16), 0 4px 14px rgba(15, 23, 42, 0.25);
}
</style>

<style scoped>
.map-shell {
  position: relative;
  height: 100%;
  min-height: 520px;
  border-radius: 24px;
  overflow: hidden;
  background: #f5f5f7;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.map-shell::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02));
}

.real-map,
.fallback-map {
  position: absolute;
  inset: 0;
}

.real-map {
  z-index: 1;
  filter: saturate(0.68) contrast(0.95) brightness(1.03);
}

.fallback-map {
  z-index: 2;
  background:
    radial-gradient(circle at 72% 22%, rgba(0, 113, 227, 0.07), transparent 32%),
    #f7f7f9;
}

.map-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 0, 0, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.035) 1px, transparent 1px);
  background-size: 48px 48px;
}

.map-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.map-marker-group {
  cursor: pointer;
}

.map-marker-group text {
  paint-order: stroke;
  stroke: #f7f7f9;
  stroke-width: 3px;
  stroke-linejoin: round;
}

.map-watermark {
  position: absolute;
  left: 16px;
  bottom: 16px;
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--faint);
  font-size: 9px;
  background: rgba(255, 255, 255, 0.84);
  border-radius: 99px;
  padding: 6px 10px;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  max-width: calc(100% - 32px);
}

.wm-pin {
  color: var(--teal);
  display: flex;
}

.wm-sep {
  width: 1px;
  height: 9px;
  background: var(--line);
}

.map-loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--muted);
  font-size: 11px;
  background: rgba(255, 255, 255, 0.75);
}

.map-topbar {
  position: absolute;
  z-index: 4;
  top: 16px;
  left: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  pointer-events: none;
}

.map-city,
.map-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.86);
  border-radius: 99px;
  padding: 8px 12px;
  color: var(--muted);
  font-size: 9.5px;
  box-shadow: 0 2px 14px rgba(0, 0, 0, 0.06);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.map-city b {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--ink);
}

.map-city > span {
  color: var(--teal);
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.legend-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.legend-count {
  color: var(--faint);
  border-left: 1px solid var(--line);
  padding-left: 6px;
}

.map-bottom {
  position: absolute;
  z-index: 4;
  right: 16px;
  bottom: 16px;
  display: flex;
  align-items: center;
  gap: 9px;
  background: rgba(255, 255, 255, 0.86);
  border-radius: 99px;
  padding: 6px 11px;
  color: var(--faint);
  font-size: 9px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.map-bottom > span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.map-bottom .estimated {
  color: var(--orange);
}

.map-tip {
  color: var(--faint);
  border-left: 1px solid var(--line);
  padding-left: 9px;
}

@media (max-width: 900px) {
  .map-shell {
    min-height: 420px;
    border-radius: 22px;
  }

  .map-tip {
    display: none !important;
  }
}
</style>
