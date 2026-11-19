<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../api'
import type { Poi } from '../types'
import AppIcon from './AppIcon.vue'

const props = defineProps<{
  open: boolean
  city: string
  dayIndex: number
  dayTheme?: string
}>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'add', poi: Poi): void
}>()

const type = ref<'attraction' | 'meal' | 'hotel'>('attraction')
const keyword = ref('')
const results = ref<Poi[]>([])
const searching = ref(false)
const error = ref('')
const addedId = ref('')

const tabs = [
  { value: 'attraction', label: '景点', icon: 'attraction' },
  { value: 'meal', label: '餐饮', icon: 'meal' },
  { value: 'hotel', label: '酒店', icon: 'hotel' },
] as const

async function search() {
  searching.value = true
  error.value = ''
  addedId.value = ''
  try {
    const data = await api.searchPoi(props.city, keyword.value.trim(), type.value)
    results.value = data.items
    if (!results.value.length) error.value = '没有找到匹配结果，换个关键词试试'
  } catch (e: any) {
    error.value = e.message || '搜索失败'
  } finally {
    searching.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      keyword.value = ''
      type.value = 'attraction'
      results.value = []
      addedId.value = ''
      search()
    }
  },
)

function switchType(next: 'attraction' | 'meal' | 'hotel') {
  type.value = next
  search()
}

function priceLabel(poi: Poi) {
  if (!poi.costCents) return '免费'
  const value = (poi.costCents / 100).toFixed(0)
  return poi.costBasis === 'room_night' ? `¥${value}/间夜` : `¥${value}/人`
}

function add(poi: Poi) {
  addedId.value = poi.poiId
  emit('add', poi)
}

function typeLabel(value: string) {
  return { attraction: '景点', meal: '餐饮', hotel: '酒店' }[value] || '安排'
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
      <div class="search-modal">
        <div class="modal-head">
          <div>
            <div class="eyebrow">ADD TO DAY {{ dayIndex }}</div>
            <h2>添加一个安排</h2>
            <p>{{ dayTheme || '为这一天补充景点、餐厅或酒店' }}</p>
          </div>
          <button class="close-btn" type="button" @click="emit('close')"><AppIcon name="x" :size="16" /></button>
        </div>

        <div class="type-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.value"
            type="button"
            :class="{ active: type === tab.value }"
            @click="switchType(tab.value)"
          >
            <AppIcon :name="tab.icon" :size="14" />
            {{ tab.label }}
          </button>
        </div>

        <form class="search-bar" @submit.prevent="search">
          <AppIcon name="search" :size="15" />
          <input
            v-model="keyword"
            :placeholder="type === 'attraction' ? '搜景点名 / 关键词，例如：博物馆' : type === 'meal' ? '搜餐厅 / 菜系，例如：火锅' : '搜酒店 / 商圈'"
          />
          <button type="submit" class="btn btn-primary" :disabled="searching">
            {{ searching ? '搜索中' : '搜索' }}
          </button>
        </form>

        <div class="result-meta">
          <span>{{ city }} · {{ typeLabel(type) }}</span>
          <span v-if="results.length">{{ results.length }} 个结果 · 价格为参考价</span>
        </div>

        <div class="results">
          <div v-if="searching" class="result-loading">
            <span class="loading-ring"></span>
            正在检索{{ typeLabel(type) }}…
          </div>
          <div v-else-if="error" class="result-empty">
            <AppIcon name="search" :size="24" />
            <p>{{ error }}</p>
            <button type="button" class="btn btn-ghost" @click="search">重试</button>
          </div>
          <div v-else class="result-list">
            <div v-for="poi in results" :key="poi.poiId" class="poi-row">
              <div class="poi-icon" :class="type">
                <AppIcon :name="type === 'attraction' ? 'attraction' : type === 'meal' ? 'meal' : 'hotel'" :size="17" />
              </div>
              <div class="poi-main">
                <div class="poi-title">
                  <b>{{ poi.name }}</b>
                  <span class="rating">★ {{ poi.rating.toFixed(1) }}</span>
                </div>
                <p>{{ poi.address || '地址以高德为准' }}</p>
                <div class="poi-tags">
                  <span v-for="tag in poi.tags.slice(0, 3)" :key="tag">{{ tag }}</span>
                  <span class="poi-price">{{ priceLabel(poi) }}</span>
                </div>
              </div>
              <button class="add-btn" type="button" :disabled="addedId === poi.poiId" @click="add(poi)">
                <AppIcon :name="addedId === poi.poiId ? 'check' : 'plus'" :size="14" />
                {{ addedId === poi.poiId ? '已添加' : '添加' }}
              </button>
            </div>
          </div>
        </div>

        <div class="modal-foot">
          <span><AppIcon name="info" :size="12" /> 添加后会自动重算路线与预算</span>
          <a v-if="!results.length" href="https://www.amap.com/" target="_blank" rel="noreferrer">去高德看看 <AppIcon name="external" :size="10" /></a>
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

.search-modal {
  width: min(720px, 100%);
  max-height: min(800px, calc(100vh - 48px));
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 28px;
  box-shadow: 0 40px 100px rgba(0, 0, 0, 0.28);
  overflow: hidden;
  animation: fadeUp 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 26px 28px 17px;
}

.modal-head .eyebrow {
  font-size: 9px;
}

.modal-head h2 {
  margin: 7px 0 0;
  font-size: 27px;
  letter-spacing: -0.045em;
  line-height: 1.1;
  font-weight: 600;
}

.modal-head p {
  margin: 7px 0 0;
  color: var(--muted);
  font-size: 11px;
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

.type-tabs {
  display: flex;
  gap: 4px;
  margin: 0 28px;
  background: var(--bg-soft);
  border-radius: 12px;
  padding: 4px;
}

.type-tabs button {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--muted);
  border-radius: 9px;
  padding: 9px 10px;
  font-size: 10.5px;
  font-weight: 500;
}

.type-tabs button.active {
  background: #fff;
  color: var(--ink);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.09);
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 16px 28px 0;
  border-radius: 14px;
  padding: 5px 5px 5px 14px;
  background: var(--bg-soft);
  border: 1px solid transparent;
  transition: 0.2s ease;
}

.search-bar:focus-within {
  background: #fff;
  border-color: rgba(0, 113, 227, 0.5);
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.08);
}

.search-bar .icon {
  color: var(--faint);
}

.search-bar input {
  flex: 1;
  border: 0;
  background: transparent;
  outline: none;
  color: var(--ink);
  font-size: 13px;
  min-width: 0;
  height: 40px;
}

.search-bar input::placeholder {
  color: #a1a1a6;
}

.search-bar .btn {
  padding: 9px 16px;
  font-size: 10.5px;
}

.result-meta {
  display: flex;
  justify-content: space-between;
  padding: 14px 28px 9px;
  color: var(--faint);
  font-size: 8.5px;
}

.results {
  flex: 1;
  min-height: 240px;
  max-height: 420px;
  overflow-y: auto;
  padding: 0 18px;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-bottom: 12px;
}

.poi-row {
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 14px;
  padding: 10px;
  transition: 0.16s ease;
}

.poi-row:hover {
  background: var(--bg-soft);
}

.poi-icon {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.poi-icon.attraction { background: #e8f2ff; color: var(--blue); }
.poi-icon.meal { background: #fff4e8; color: var(--orange); }
.poi-icon.hotel { background: #e8f8f7; color: var(--teal); }

.poi-main {
  flex: 1;
  min-width: 0;
}

.poi-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.poi-title b {
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rating {
  color: var(--orange);
  font-size: 9px;
  flex-shrink: 0;
}

.poi-main p {
  margin: 3px 0 5px;
  color: var(--faint);
  font-size: 9px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.poi-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

.poi-tags span {
  background: var(--bg-soft);
  border-radius: 99px;
  padding: 2px 6px;
  color: var(--muted);
  font-size: 8px;
}

.poi-tags .poi-price {
  color: var(--orange);
  background: #fff6ec;
}

.add-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: var(--blue);
  color: #fff;
  border-radius: 99px;
  padding: 7px 12px;
  font-size: 9.5px;
  font-weight: 500;
  flex-shrink: 0;
}

.add-btn:hover {
  background: var(--blue-hover);
}

.add-btn:disabled {
  background: #e8f8f7;
  color: var(--teal);
  cursor: default;
}

.result-loading,
.result-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 11px;
  min-height: 240px;
  color: var(--faint);
  font-size: 10.5px;
}

.result-empty p {
  margin: 0;
}

.loading-ring {
  width: 24px;
  height: 24px;
  border: 2px solid #e5e5ea;
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.modal-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  background: var(--bg-soft);
  padding: 12px 28px;
  color: var(--faint);
  font-size: 8.5px;
}

.modal-foot span,
.modal-foot a {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.modal-foot a {
  color: var(--blue);
}

@media (max-width: 600px) {
  .modal-backdrop {
    padding: 0;
    align-items: flex-end;
  }

  .search-modal {
    width: 100%;
    max-height: 92vh;
    border-radius: 24px 24px 0 0;
  }

  .modal-head {
    padding: 22px 18px 15px;
  }

  .type-tabs,
  .search-bar {
    margin-left: 18px;
    margin-right: 18px;
  }

  .result-meta {
    padding-left: 18px;
    padding-right: 18px;
  }

  .results {
    max-height: 44vh;
  }

  .poi-row {
    align-items: flex-start;
  }

  .add-btn {
    padding: 6px 9px;
  }

  .add-btn .icon {
    display: none;
  }
}
</style>
