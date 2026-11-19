<script setup lang="ts">
import { computed } from 'vue'
import type { BudgetSummary } from '../types'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ budget: BudgetSummary; dayCount: number; selectedDay?: number }>()
const emit = defineEmits<{ (e: 'select-day', day: number): void }>()

const fmt = (cents: number) =>
  (cents / 100).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
const maxCategory = computed(() => Math.max(1, ...(props.budget.categories || []).map((c) => c.amountCents)))
const maxDay = computed(() => Math.max(1, ...(props.budget.daily || []).map((d) => d.amountCents)))
const percent = (value: number) => Math.round((value / Math.max(1, props.budget.totalCents)) * 100)
const overAmount = computed(() => Math.max(0, props.budget.totalCents - (props.budget.budgetLimitCents || 0)))
</script>

<template>
  <aside class="budget-panel">
    <div class="budget-head">
      <div>
        <div class="eyebrow">BUDGET · 参考价</div>
        <div class="total"><span>¥</span>{{ fmt(budget.totalCents) }}</div>
        <div class="per-person">人均 ¥{{ fmt(budget.perPersonCents) }} · {{ budget.headcount }} 人</div>
      </div>
      <span class="budget-icon"><AppIcon name="wallet" :size="18" /></span>
    </div>

    <div v-if="budget.overBudget" class="over-budget">
      <AppIcon name="info" :size="14" />
      <div>
        <b>超出预算 ¥{{ fmt(overAmount) }}</b>
        <p>可以换更经济的酒店，或减少付费景点。</p>
      </div>
    </div>

    <div class="divider"></div>

    <div class="section-label">费用构成</div>
    <div class="category-list">
      <div v-for="category in budget.categories" :key="category.key" class="category-row">
        <div class="category-top">
          <span class="cat-name">{{ category.label }}</span>
          <span class="cat-amount">¥{{ fmt(category.amountCents) }}</span>
          <span class="cat-percent">{{ percent(category.amountCents) }}%</span>
        </div>
        <div class="bar-track">
          <div
            class="bar-fill"
            :class="'bar-' + category.key"
            :style="{ width: Math.max(3, (category.amountCents / maxCategory) * 100) + '%' }"
          ></div>
        </div>
      </div>
    </div>

    <div class="divider"></div>

    <div class="section-label">每日花费</div>
    <div class="daily-list">
      <button
        v-for="day in budget.daily"
        :key="day.dayIndex"
        class="daily-row"
        :class="{ active: selectedDay === day.dayIndex }"
        type="button"
        @click="emit('select-day', day.dayIndex)"
      >
        <span>DAY {{ day.dayIndex }}</span>
        <div class="daily-bar"><i :style="{ width: (day.amountCents / maxDay) * 100 + '%' }"></i></div>
        <b>¥{{ fmt(day.amountCents) }}</b>
      </button>
    </div>

    <div class="transport-note">
      <div class="transport-head">
        <AppIcon name="route" :size="13" />
        <span>城际交通</span>
        <b>¥{{ fmt(budget.transport.amountCents) }}</b>
      </div>
      <p>{{ budget.transport.note }}</p>
      <a :href="budget.transport.bookingUrl" target="_blank" rel="noreferrer">
        查询参考班次 <AppIcon name="external" :size="10" />
      </a>
    </div>

    <p class="price-note">{{ budget.priceNote }}</p>
  </aside>
</template>

<style scoped>
.budget-panel {
  height: 100%;
  background: #fff;
  border-radius: 24px;
  padding: 22px 20px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.budget-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.budget-head .eyebrow {
  font-size: 9px;
}

.total {
  font-size: 38px;
  font-weight: 600;
  letter-spacing: -0.055em;
  line-height: 1.1;
  margin-top: 7px;
  color: var(--ink);
}

.total span {
  font-size: 17px;
  color: var(--faint);
  margin-right: 1px;
  font-weight: 400;
}

.per-person {
  color: var(--faint);
  font-size: 9.5px;
  margin-top: 5px;
}

.budget-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-soft);
  color: var(--ink);
  display: grid;
  place-items: center;
}

.over-budget {
  display: flex;
  gap: 8px;
  border-radius: 12px;
  background: #fff4e8;
  padding: 10px;
  margin-top: 15px;
  color: var(--orange);
}

.over-budget b {
  display: block;
  font-size: 10.5px;
}

.over-budget p {
  margin: 3px 0 0;
  color: #8a5a34;
  font-size: 9px;
  line-height: 1.5;
}

.divider {
  height: 1px;
  background: #f0f0f2;
  margin: 17px 0 14px;
}

.section-label {
  color: var(--faint);
  font-size: 8.5px;
  letter-spacing: 0.12em;
  margin-bottom: 12px;
  text-transform: uppercase;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.category-top {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 10.5px;
}

.cat-name {
  color: var(--ink-2);
  width: 55px;
  flex-shrink: 0;
}

.cat-amount {
  color: var(--ink);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  margin-left: auto;
}

.cat-percent {
  color: var(--faint);
  font-size: 8.5px;
  width: 28px;
  text-align: right;
}

.bar-track {
  height: 5px;
  border-radius: 99px;
  background: #f0f0f2;
  margin-top: 5px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 99px;
  background: var(--ink);
}

.bar-ticket { background: #0071e3; }
.bar-hotel { background: #008f8c; }
.bar-meal { background: #ff9f0a; }
.bar-local { background: #5e5ce6; }
.bar-intercity { background: #ff6b22; }
.bar-buffer { background: #c7c7cc; }

.daily-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.daily-row {
  display: grid;
  grid-template-columns: 38px 1fr auto;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  border-radius: 7px;
  padding: 6px 4px;
  color: var(--muted);
  font-size: 8.5px;
  text-align: left;
}

.daily-row:hover,
.daily-row.active {
  background: var(--bg-soft);
}

.daily-row span {
  font-size: 8px;
  letter-spacing: 0.04em;
}

.daily-row b {
  color: var(--ink-2);
  font-size: 9px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.daily-bar {
  height: 4px;
  background: #f0f0f2;
  border-radius: 99px;
  overflow: hidden;
}

.daily-bar i {
  display: block;
  height: 100%;
  background: #c7c7cc;
  border-radius: 99px;
}

.daily-row.active .daily-bar i {
  background: var(--blue);
}

.transport-note {
  margin-top: 16px;
  background: var(--bg-soft);
  border-radius: 12px;
  padding: 11px 12px;
}

.transport-head {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--muted);
  font-size: 9.5px;
}

.transport-head b {
  margin-left: auto;
  color: var(--ink);
  font-size: 10.5px;
  font-weight: 500;
}

.transport-note p {
  margin: 5px 0 5px;
  color: var(--faint);
  font-size: 8.5px;
  line-height: 1.6;
}

.transport-note a {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--blue);
  font-size: 8.5px;
  font-weight: 500;
}

.price-note {
  margin: auto 0 0;
  padding-top: 14px;
  color: #a1a1a6;
  font-size: 8px;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .budget-panel {
    min-height: auto;
  }
}
</style>
