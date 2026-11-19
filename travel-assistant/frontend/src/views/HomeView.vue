<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import AppIcon from '../components/AppIcon.vue'
import { api } from '../api'
import { useSessionStore } from '../stores'
import type { HotelLevel, Pace } from '../types'

const router = useRouter()
const session = useSessionStore()
const submitting = ref(false)
const error = ref('')

const pad = (n: number) => String(n).padStart(2, '0')
const iso = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const addDays = (date: Date, days: number) => {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

const base = addDays(new Date(), 7)
const form = reactive({
  city: '成都',
  origin: '北京',
  startDate: iso(base),
  endDate: iso(addDays(base, 2)),
  adults: 2,
  children: 0,
  budgetYuan: 8000,
  scenery: ['历史', '自然'] as string[],
  food: ['川菜', '火锅'] as string[],
  pace: 'balanced' as Pace,
  hotelLevel: 'comfort' as HotelLevel,
  local: 'mixed' as 'public' | 'taxi' | 'mixed',
  notes: '',
})

const cities = ['成都', '西安', '杭州', '厦门', '北京', '重庆', '大理']
const sceneryOptions = ['历史', '自然', '古镇', '博物馆', '亲子', '夜景', '艺术', '街区']
const foodOptions = ['川菜', '火锅', '小吃', '烧烤', '咖啡', '素斋']
const paces: { value: Pace; label: string; hint: string }[] = [
  { value: 'relaxed', label: '松弛', hint: '每天 2 个主景点' },
  { value: 'balanced', label: '适中', hint: '每天 2–3 个景点' },
  { value: 'packed', label: '紧凑', hint: '每天 3–4 个景点' },
]
const hotelLevels: { value: HotelLevel; label: string }[] = [
  { value: 'budget', label: '经济' },
  { value: 'comfort', label: '舒适' },
  { value: 'premium', label: '品质' },
]
const cityCards = [
  { name: '成都', tag: '烟火与慢生活', tone: 'teal' },
  { name: '杭州', tag: '湖山与宋韵', tone: 'blue' },
  { name: '西安', tag: '十三朝古都', tone: 'amber' },
  { name: '厦门', tag: '海风与骑楼', tone: 'cyan' },
  { name: '北京', tag: '中轴线与胡同', tone: 'slate' },
  { name: '重庆', tag: '山城与夜色', tone: 'violet' },
  { name: '大理', tag: '苍山与洱海', tone: 'green' },
]

const dayCount = computed(() => {
  const start = new Date(form.startDate).getTime()
  const end = new Date(form.endDate).getTime()
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return 0
  return Math.round((end - start) / 86400000) + 1
})

const demoHint = computed(() => {
  if (!session.info) return '正在连接服务…'
  if (!session.info.amapConfigured) return '当前为内置演示模式，配置高德 Key 后可规划任意城市。'
  if (!session.info.llmConfigured) return '已连接高德地图；配置大模型 Key 后可启用 AI 编排。'
  return '已连接高德地图与大模型，可规划任意国内城市。'
})

const tripSummary = computed(() => {
  const bits = [`${dayCount.value} 天`]
  if (form.adults + form.children > 0) bits.push(`${form.adults + form.children} 人`)
  bits.push(`¥${form.budgetYuan.toLocaleString('zh-CN')}`)
  return bits.join(' · ')
})

function toggle(list: string[], value: string) {
  const index = list.indexOf(value)
  if (index >= 0) list.splice(index, 1)
  else list.push(value)
}

function validate() {
  if (!form.city.trim()) return '请填写目的地城市'
  if (!form.startDate || !form.endDate) return '请选择出行日期'
  if (new Date(form.endDate) < new Date(form.startDate)) return '结束日期不能早于开始日期'
  if (dayCount.value > 7) return '单次行程最多支持 7 天'
  if (form.adults < 1) return '至少需要 1 位成人'
  if (form.budgetYuan < 500) return '预算至少 500 元'
  return ''
}

function pickCity(city: string) {
  form.city = city
  document.getElementById('planner')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function submit() {
  error.value = validate()
  if (error.value) return
  submitting.value = true
  try {
    await session.ensure()
    const result = await api.createPlan({
      destination: { city: form.city.trim() },
      origin: form.origin.trim() || undefined,
      startDate: form.startDate,
      endDate: form.endDate,
      travelers: { adults: form.adults, children: form.children },
      budget: {
        totalCents: Math.round(form.budgetYuan * 100),
        currency: 'CNY',
        level: form.hotelLevel,
      },
      preferences: {
        scenery: form.scenery,
        food: form.food,
        pace: form.pace,
        hotelLevel: form.hotelLevel,
        avoid: [],
      },
      transport: { intercity: 'auto', local: form.local },
      notes: form.notes.trim() || undefined,
    })
    sessionStorage.setItem(
      'ta_last_plan',
      JSON.stringify({
        city: form.city.trim(),
        startDate: form.startDate,
        endDate: form.endDate,
        adults: form.adults,
        children: form.children,
      }),
    )
    router.push(`/plan/${result.runId}`)
  } catch (e: any) {
    error.value = e.message || '创建规划失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

function setDuration(days: number) {
  form.endDate = iso(addDays(new Date(form.startDate), days - 1))
}
</script>

<template>
  <div class="home-page">
    <AppHeader />

    <main>
      <section class="hero">
        <div class="hero-copy fade-up">
          <div class="hero-kicker"><span class="kicker-dot"></span> AI 旅行规划 · 国内游</div>
          <h1>旅行，<br /><span class="gradient-text">从期待开始。</span></h1>
          <p class="hero-sub">告诉我们想去哪里。剩下的，交给漫游。</p>
          <div class="hero-actions">
            <a href="#planner" class="btn btn-primary">开始规划 <AppIcon name="chevron-right" :size="14" /></a>
            <a href="#how" class="text-link">看看它怎么工作 <AppIcon name="arrow-down" :size="13" /></a>
          </div>
          <div class="hero-meta">
            <span>国内游</span>
            <span>高德地图</span>
            <span>AI 编排</span>
          </div>
        </div>

        <div class="hero-visual fade-up">
          <div class="visual-glow"></div>
          <div class="visual-card">
            <div class="visual-head">
              <div><span class="visual-kicker">YOUR TRIP</span><b>杭州 · 3 日</b></div>
              <span class="visual-badge">AI 已生成</span>
            </div>
            <div class="visual-map">
              <svg viewBox="0 0 520 350" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                <defs>
                  <linearGradient id="routeGradient" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stop-color="#5eead4" />
                    <stop offset="100%" stop-color="#60a5fa" />
                  </linearGradient>
                  <linearGradient id="landGradient" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stop-color="#0b2b3a" />
                    <stop offset="100%" stop-color="#0f172a" />
                  </linearGradient>
                </defs>
                <rect width="520" height="350" fill="url(#landGradient)" />
                <g opacity=".22" stroke="#94a3b8" stroke-width=".7">
                  <path d="M0 68h520M0 136h520M0 204h520M0 272h520M86 0v350M172 0v350M258 0v350M344 0v350M430 0v350" />
                </g>
                <path d="M-20 285C90 235 145 308 238 270s170-81 302-32" fill="none" stroke="#0e7490" stroke-width="26" opacity=".28" stroke-linecap="round" />
                <path d="M-20 285C90 235 145 308 238 270s170-81 302-32" fill="none" stroke="#22d3ee" stroke-width="1.2" opacity=".45" stroke-linecap="round" />
                <path d="M92 258C132 216 166 212 210 196s81-10 122-42 77-79 116-78" fill="none" stroke="url(#routeGradient)" stroke-width="3" stroke-linecap="round" />
                <path d="M210 196c42 18 70 8 102 31s47 45 84 52" fill="none" stroke="url(#routeGradient)" stroke-width="3" stroke-linecap="round" opacity=".65" />
                <g>
                  <circle cx="92" cy="258" r="8" fill="#0f172a" stroke="#5eead4" stroke-width="2.5" />
                  <circle cx="92" cy="258" r="18" fill="#5eead4" opacity=".12" />
                  <text x="108" y="263" fill="#d1fae5" font-size="11" font-family="-apple-system, PingFang SC">西湖</text>
                  <circle cx="210" cy="196" r="8" fill="#0f172a" stroke="#93c5fd" stroke-width="2.5" />
                  <circle cx="210" cy="196" r="18" fill="#93c5fd" opacity=".12" />
                  <text x="226" y="201" fill="#dbeafe" font-size="11" font-family="-apple-system, PingFang SC">灵隐寺</text>
                  <circle cx="312" cy="227" r="8" fill="#0f172a" stroke="#5eead4" stroke-width="2.5" />
                  <text x="328" y="232" fill="#d1fae5" font-size="11" font-family="-apple-system, PingFang SC">西溪湿地</text>
                  <circle cx="396" cy="279" r="8" fill="#0f172a" stroke="#93c5fd" stroke-width="2.5" />
                  <text x="412" y="284" fill="#dbeafe" font-size="11" font-family="-apple-system, PingFang SC">河坊街</text>
                </g>
              </svg>
            </div>
            <div class="visual-days">
              <div><small>DAY 1</small><b>西湖 · 灵隐</b></div>
              <div><small>DAY 2</small><b>西溪 · 河坊</b></div>
              <div><small>DAY 3</small><b>博物馆 · 咖啡</b></div>
            </div>
          </div>
          <div class="float-card float-budget">
            <span>参考预算</span>
            <b>¥6,099</b>
            <small>含交通 · 人均 ¥3,050</small>
          </div>
          <div class="float-card float-route">
            <span class="float-icon"><AppIcon name="route" :size="16" /></span>
            <div><b>11 段路线</b><small>已按路程优化</small></div>
          </div>
        </div>
      </section>

      <section id="planner" class="planner-section">
        <div class="planner-head">
          <div class="eyebrow">PLAN YOUR TRIP</div>
          <h2>为下一次出发，<br />做一份刚刚好的计划。</h2>
          <p>不需要做攻略。告诉我们你的时间、预算和偏好，剩下的交给 AI。</p>
        </div>

        <div class="planner-card">
          <form @submit.prevent="submit">
            <div class="planner-steps">
              <div><span>01</span><b>去哪里</b><small>目的地与出发地</small></div>
              <div><span>02</span><b>什么时候</b><small>日期与同行人</small></div>
              <div><span>03</span><b>想要什么</b><small>偏好与节奏</small></div>
            </div>

            <div class="planner-grid">
              <div class="form-main">
                <div class="field">
                  <label>目的地</label>
                  <div class="city-input">
                    <AppIcon name="pin" :size="18" />
                    <input v-model="form.city" placeholder="输入国内城市，例如：杭州" />
                  </div>
                  <div class="city-chips">
                    <button
                      v-for="city in cities"
                      :key="city"
                      type="button"
                      class="chip"
                      :class="{ active: form.city === city }"
                      @click="form.city = city"
                    >
                      {{ city }}
                    </button>
                  </div>
                </div>

                <div class="two-col">
                  <div class="field">
                    <label>出发城市 <span>用于估算城际交通</span></label>
                    <input v-model="form.origin" class="input" placeholder="例如：北京" />
                  </div>
                  <div class="field">
                    <label>出行日期</label>
                    <div class="date-row">
                      <input v-model="form.startDate" type="date" class="input" />
                      <span>—</span>
                      <input v-model="form.endDate" type="date" class="input" />
                    </div>
                  </div>
                </div>

                <div class="duration-row">
                  <span class="duration-label">玩几天</span>
                  <div class="duration-chips">
                    <button
                      v-for="d in [2, 3, 4, 5]"
                      :key="d"
                      type="button"
                      class="duration-chip"
                      :class="{ active: dayCount === d }"
                      @click="setDuration(d)"
                    >
                      {{ d }} 天
                    </button>
                  </div>
                  <span class="duration-result">{{ dayCount ? `${dayCount} 天 ${Math.max(0, dayCount - 1)} 晚` : '' }}</span>
                </div>

                <div class="two-col">
                  <div class="field">
                    <label>同行人数</label>
                    <div class="stepper-row">
                      <div class="stepper">
                        <button type="button" @click="form.adults = Math.max(1, form.adults - 1)">−</button>
                        <span><b>{{ form.adults }}</b> 成人</span>
                        <button type="button" @click="form.adults = Math.min(10, form.adults + 1)">+</button>
                      </div>
                      <div class="stepper">
                        <button type="button" @click="form.children = Math.max(0, form.children - 1)">−</button>
                        <span><b>{{ form.children }}</b> 儿童</span>
                        <button type="button" @click="form.children = Math.min(10, form.children + 1)">+</button>
                      </div>
                    </div>
                  </div>
                  <div class="field">
                    <label>预算 <span>元 / 全程</span></label>
                    <div class="budget-line">
                      <span>¥</span>
                      <input v-model.number="form.budgetYuan" type="number" min="500" step="500" class="input" />
                      <div class="segmented small">
                        <button
                          v-for="level in hotelLevels"
                          :key="level.value"
                          type="button"
                          :class="{ active: form.hotelLevel === level.value }"
                          @click="form.hotelLevel = level.value"
                        >
                          {{ level.label }}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="form-side">
                <div class="field">
                  <label>想看的风景</label>
                  <div class="option-chips">
                    <button
                      v-for="item in sceneryOptions"
                      :key="item"
                      type="button"
                      class="chip"
                      :class="{ active: form.scenery.includes(item) }"
                      @click="toggle(form.scenery, item)"
                    >
                      {{ item }}
                    </button>
                  </div>
                </div>

                <div class="field">
                  <label>想吃的味道</label>
                  <div class="option-chips">
                    <button
                      v-for="item in foodOptions"
                      :key="item"
                      type="button"
                      class="chip"
                      :class="{ active: form.food.includes(item) }"
                      @click="toggle(form.food, item)"
                    >
                      {{ item }}
                    </button>
                  </div>
                </div>

                <div class="two-col">
                  <div class="field">
                    <label>行程节奏</label>
                    <div class="segmented">
                      <button
                        v-for="pace in paces"
                        :key="pace.value"
                        type="button"
                        :class="{ active: form.pace === pace.value }"
                        :title="pace.hint"
                        @click="form.pace = pace.value"
                      >
                        {{ pace.label }}
                      </button>
                    </div>
                  </div>
                  <div class="field">
                    <label>市内交通</label>
                    <div class="segmented">
                      <button :class="{ active: form.local === 'mixed' }" type="button" @click="form.local = 'mixed'">混合</button>
                      <button :class="{ active: form.local === 'public' }" type="button" @click="form.local = 'public'">公交</button>
                      <button :class="{ active: form.local === 'taxi' }" type="button" @click="form.local = 'taxi'">打车</button>
                    </div>
                  </div>
                </div>

                <div class="field">
                  <label>补充说明 <span>可选</span></label>
                  <textarea
                    v-model="form.notes"
                    class="textarea"
                    placeholder="例如：带父母，不想太赶；想去熊猫基地；不吃辣……"
                  ></textarea>
                </div>
              </div>
            </div>

            <p v-if="error" class="form-error">{{ error }}</p>

            <div class="form-footer">
              <div class="form-summary">
                <span class="summary-label">你的行程</span>
                <b>{{ tripSummary }}</b>
                <span class="summary-note">{{ demoHint }}</span>
              </div>
              <button class="submit-btn" :disabled="submitting" type="submit">
                <span v-if="submitting"><AppIcon name="refresh" :size="16" class="spin" /> 正在创建规划…</span>
                <span v-else>生成我的行程 <AppIcon name="arrow-right" :size="16" /></span>
              </button>
            </div>
            <p class="form-foot">预计 20–60 秒 · 生成后可以自由增删景点 · 无需登录</p>
          </form>
        </div>
      </section>

      <section id="how" class="how-section">
        <div class="section-head center">
          <div class="eyebrow">HOW IT WORKS</div>
          <h2>从一句话，<br />到一份可执行的行程。</h2>
          <p>不是把搜索结果堆在一起，而是真的替你安排顺序、路线和时间。</p>
        </div>

        <div class="how-grid">
          <div class="how-card how-card-dark">
            <span class="how-num">01</span>
            <div class="how-icon"><AppIcon name="sparkles" :size="22" /></div>
            <h3>听懂你的偏好</h3>
            <p>想看湖、想吃小吃、带父母不想太赶——这些都会被翻译成可执行的约束。</p>
            <div class="how-mini-tags"><span>西湖</span><span>小吃</span><span>慢节奏</span></div>
          </div>
          <div class="how-card">
            <span class="how-num">02</span>
            <div class="how-icon blue"><AppIcon name="route" :size="22" /></div>
            <h3>按地理位置排程</h3>
            <p>同一天只走一片区域，少折返。路线距离、交通耗时和营业时间一起计算。</p>
            <div class="mini-route">
              <i></i><i></i><i></i><i></i>
            </div>
          </div>
          <div class="how-card">
            <span class="how-num">03</span>
            <div class="how-icon teal"><AppIcon name="wallet" :size="22" /></div>
            <h3>把预算算清楚</h3>
            <p>门票、住宿、餐饮、交通分类呈现。每一项都有来源，超支会直接告诉你。</p>
            <div class="mini-budget">
              <span>门票</span><b>¥300</b><span>住宿</span><b>¥1,200</b><span>交通</span><b>¥1,895</b>
            </div>
          </div>
        </div>
      </section>

      <section class="destinations-section">
        <div class="section-head">
          <div>
            <div class="eyebrow">DESTINATIONS</div>
            <h2>下一站，去哪里？</h2>
          </div>
          <p>点击城市，直接带入规划。</p>
        </div>
        <div class="city-grid">
          <button
            v-for="(city, index) in cityCards"
            :key="city.name"
            type="button"
            class="city-tile"
            :class="`tone-${city.tone}`"
            @click="pickCity(city.name)"
          >
            <span class="city-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="city-arrow"><AppIcon name="arrow-right" :size="15" /></span>
            <span class="city-name">{{ city.name }}</span>
            <span class="city-tag">{{ city.tag }}</span>
            <span class="city-line"></span>
          </button>
        </div>
      </section>

      <section class="closing-section">
        <div class="closing-glow"></div>
        <div class="closing-content">
          <div class="eyebrow">READY WHEN YOU ARE</div>
          <h2>出发吧。<br /><span>剩下的交给漫游。</span></h2>
          <p>下一次旅行，不用从做攻略开始。</p>
          <a href="#planner" class="btn btn-primary">规划我的行程 <AppIcon name="arrow-right" :size="14" /></a>
        </div>
      </section>

      <footer class="home-footer">
        <div class="footer-inner">
          <div class="footer-brand"><span>漫游</span><small>SMART TRAVEL</small></div>
          <div class="footer-links">
            <a href="#planner">开始规划</a>
            <router-link to="/trips">我的行程</router-link>
            <a href="https://www.amap.com/" target="_blank" rel="noreferrer">高德地图</a>
          </div>
          <p>国内游 · 价格为参考估算 · 地图数据 © 高德地图</p>
        </div>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.home-page {
  background: var(--bg);
}

/* ------------------------------------------------------------------ */
/* Hero                                                                */
/* ------------------------------------------------------------------ */
.hero {
  width: min(1180px, calc(100% - 44px));
  margin: 0 auto;
  display: grid;
  grid-template-columns: 0.96fr 1.04fr;
  align-items: center;
  gap: 64px;
  padding: 92px 0 78px;
}

.hero-copy {
  padding-bottom: 10px;
}

.hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
}

.kicker-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 3px rgba(0, 143, 140, 0.1);
}

.hero h1 {
  margin: 22px 0 20px;
  font-size: clamp(56px, 7vw, 90px);
  line-height: 0.99;
  letter-spacing: -0.055em;
  font-weight: 600;
  color: var(--ink);
}

.gradient-text {
  background: linear-gradient(100deg, #0071e3 4%, #00a6a0 92%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-sub {
  max-width: 390px;
  margin: 0;
  color: var(--muted);
  font-size: 19px;
  line-height: 1.55;
  letter-spacing: -0.012em;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 22px;
  margin-top: 30px;
}

.hero-actions .btn {
  padding: 13px 24px;
  font-size: 15px;
}

.text-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--blue);
  font-size: 14px;
  font-weight: 500;
}

.text-link:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.hero-meta {
  display: flex;
  gap: 20px;
  margin-top: 35px;
  color: var(--faint);
  font-size: 11px;
}

.hero-meta span {
  position: relative;
}

.hero-meta span + span::before {
  content: "";
  position: absolute;
  left: -10px;
  top: 50%;
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: #c7c7cc;
}

.hero-visual {
  position: relative;
  min-height: 560px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.visual-glow {
  position: absolute;
  width: 78%;
  height: 74%;
  border-radius: 50%;
  background: linear-gradient(130deg, rgba(0, 113, 227, 0.2), rgba(0, 166, 160, 0.12));
  filter: blur(70px);
  opacity: 0.75;
}

.visual-card {
  position: relative;
  width: 92%;
  border-radius: 30px;
  padding: 16px;
  background: #0b1220;
  box-shadow: 0 32px 80px rgba(0, 0, 0, 0.22), 0 2px 0 rgba(255, 255, 255, 0.1) inset;
  color: #fff;
  overflow: hidden;
  transform: rotate(-1.3deg);
}

.visual-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 6px 6px 13px;
}

.visual-kicker {
  display: block;
  color: rgba(255, 255, 255, 0.45);
  font-size: 8px;
  letter-spacing: 0.18em;
  margin-bottom: 4px;
}

.visual-head b {
  display: block;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.visual-badge {
  border: 1px solid rgba(94, 234, 212, 0.25);
  background: rgba(94, 234, 212, 0.08);
  color: #5eead4;
  border-radius: 99px;
  padding: 5px 9px;
  font-size: 9px;
  font-weight: 500;
}

.visual-map {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  background: #0b2b3a;
  aspect-ratio: 1.36;
}

.visual-map svg {
  width: 100%;
  height: 100%;
  display: block;
}

.visual-days {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 13px 3px 2px;
}

.visual-days div {
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  padding-top: 9px;
}

.visual-days small {
  display: block;
  color: rgba(255, 255, 255, 0.38);
  font-size: 8px;
  letter-spacing: 0.1em;
}

.visual-days b {
  display: block;
  font-size: 10px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.82);
  margin-top: 3px;
}

.float-card {
  position: absolute;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow: 0 16px 45px rgba(0, 0, 0, 0.12);
  border-radius: 16px;
  padding: 12px 15px;
  color: var(--ink);
}

.float-budget {
  left: -24px;
  bottom: 104px;
  min-width: 146px;
}

.float-budget span {
  display: block;
  color: var(--faint);
  font-size: 9px;
}

.float-budget b {
  display: block;
  margin-top: 2px;
  font-size: 23px;
  letter-spacing: -0.04em;
}

.float-budget small {
  display: block;
  color: var(--faint);
  font-size: 8px;
  margin-top: 2px;
}

.float-route {
  right: -4px;
  top: 42px;
  display: flex;
  align-items: center;
  gap: 9px;
}

.float-icon {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: #e8f8f7;
  color: var(--teal);
  display: grid;
  place-items: center;
}

.float-route b {
  display: block;
  font-size: 10px;
}

.float-route small {
  display: block;
  color: var(--faint);
  font-size: 8px;
  margin-top: 1px;
}

/* ------------------------------------------------------------------ */
/* Planner                                                             */
/* ------------------------------------------------------------------ */
.planner-section {
  background: var(--bg-soft);
  padding: 100px 0 104px;
}

.planner-head {
  width: min(780px, calc(100% - 44px));
  margin: 0 auto 46px;
  text-align: center;
}

.planner-head h2,
.section-head h2 {
  margin: 13px 0 15px;
  font-size: clamp(34px, 4.4vw, 54px);
  line-height: 1.07;
  letter-spacing: -0.045em;
  font-weight: 600;
}

.planner-head p,
.section-head p {
  margin: 0 auto;
  color: var(--muted);
  font-size: 16px;
  line-height: 1.6;
  max-width: 580px;
}

.planner-card {
  width: min(1080px, calc(100% - 44px));
  margin: 0 auto;
  background: #fff;
  border-radius: 30px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.07);
  padding: 32px 34px 22px;
}

.planner-steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--line-soft);
}

.planner-steps > div {
  display: grid;
  grid-template-columns: 30px 1fr;
  column-gap: 9px;
  align-items: center;
}

.planner-steps span {
  grid-row: span 2;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--bg-soft);
  color: var(--faint);
  display: grid;
  place-items: center;
  font-size: 9px;
  letter-spacing: 0.02em;
}

.planner-steps b {
  display: block;
  font-size: 13px;
  font-weight: 600;
}

.planner-steps small {
  display: block;
  color: var(--faint);
  font-size: 10px;
  margin-top: 2px;
}

.planner-grid {
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: 38px;
  padding: 28px 0 24px;
}

.form-main,
.form-side {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.form-side {
  padding-left: 38px;
  border-left: 1px solid var(--line-soft);
}

.city-input {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 54px;
  border-radius: 14px;
  background: var(--bg-soft);
  padding: 0 16px;
  border: 1px solid transparent;
  transition: 0.2s ease;
}

.city-input:focus-within {
  background: #fff;
  border-color: rgba(0, 113, 227, 0.55);
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.1);
}

.city-input .icon {
  color: var(--faint);
}

.city-input input {
  flex: 1;
  width: 100%;
  border: 0;
  background: transparent;
  outline: none;
  font-size: 18px;
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--ink);
}

.city-input input::placeholder {
  color: #a1a1a6;
  font-weight: 400;
}

.city-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.city-chips .chip,
.option-chips .chip {
  padding: 8px 13px;
  font-size: 12px;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.date-row {
  display: flex;
  align-items: center;
  gap: 7px;
}

.date-row span {
  color: var(--faint);
  font-size: 11px;
}

.date-row .input {
  padding: 10px;
  font-size: 12px;
  height: 48px;
}

.duration-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.duration-label {
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
}

.duration-chips {
  display: flex;
  gap: 5px;
  background: var(--bg-soft);
  padding: 3px;
  border-radius: 99px;
}

.duration-chip {
  border: 0;
  background: transparent;
  color: var(--muted);
  border-radius: 99px;
  padding: 7px 11px;
  font-size: 11px;
  font-weight: 500;
}

.duration-chip.active {
  background: #fff;
  color: var(--ink);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.duration-result {
  margin-left: auto;
  color: var(--teal);
  font-size: 11px;
  font-weight: 500;
}

.stepper-row {
  display: flex;
  gap: 9px;
}

.stepper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  border-radius: 12px;
  background: var(--bg-soft);
  padding: 0 6px;
}

.stepper button {
  width: 28px;
  height: 30px;
  border: 0;
  border-radius: 8px;
  background: #fff;
  color: var(--ink-2);
  font-size: 15px;
  line-height: 1;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.stepper span {
  color: var(--muted);
  font-size: 11px;
}

.stepper b {
  color: var(--ink);
  font-size: 13px;
}

.budget-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.budget-line > span {
  color: var(--faint);
  font-size: 15px;
  margin-left: -2px;
}

.budget-line .input {
  width: 85px;
  flex-shrink: 0;
  font-weight: 500;
}

.segmented {
  display: flex;
  background: var(--bg-soft);
  border-radius: 10px;
  padding: 3px;
  gap: 2px;
}

.segmented.small {
  flex: 1;
  min-width: 0;
}

.segmented button {
  flex: 1;
  border: 0;
  background: transparent;
  color: var(--muted);
  border-radius: 8px;
  padding: 8px 4px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  transition: 0.16s ease;
}

.segmented button.active {
  background: #fff;
  color: var(--ink);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.option-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.form-error {
  margin: 2px 0 0;
  color: var(--rose);
  background: #fff2f3;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12px;
}

.form-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding-top: 22px;
  border-top: 1px solid var(--line-soft);
}

.form-summary {
  min-width: 0;
}

.summary-label {
  display: block;
  color: var(--faint);
  font-size: 9px;
  letter-spacing: 0.12em;
  margin-bottom: 3px;
}

.form-summary b {
  display: block;
  font-size: 16px;
  letter-spacing: -0.02em;
}

.summary-note {
  display: block;
  color: var(--faint);
  font-size: 10px;
  margin-top: 3px;
}

.submit-btn {
  border: 0;
  border-radius: 980px;
  background: var(--blue);
  color: #fff;
  padding: 14px 26px;
  font-size: 15px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-width: 190px;
  transition: 0.2s ease;
}

.submit-btn:hover:not(:disabled) {
  background: var(--blue-hover);
}

.submit-btn:active:not(:disabled) {
  transform: scale(0.985);
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}

.form-foot {
  text-align: right;
  color: var(--faint);
  font-size: 9px;
  margin: 9px 0 0;
}

/* ------------------------------------------------------------------ */
/* How                                                                 */
/* ------------------------------------------------------------------ */
.how-section {
  padding: 106px 0 100px;
  background: #fff;
}

.section-head {
  width: min(1180px, calc(100% - 44px));
  margin: 0 auto 44px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 30px;
}

.section-head.center {
  display: block;
  text-align: center;
  max-width: 760px;
}

.section-head.center h2 {
  margin-top: 13px;
}

.section-head.center p {
  margin-top: 0;
}

.how-grid {
  width: min(1180px, calc(100% - 44px));
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}

.how-card {
  min-height: 330px;
  border-radius: 26px;
  background: var(--bg-soft);
  padding: 28px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.how-card-dark {
  background: #1d1d1f;
  color: #fff;
}

.how-card-dark p {
  color: #a1a1a6;
}

.how-num {
  position: absolute;
  right: 25px;
  top: 23px;
  color: #a1a1a6;
  font-size: 11px;
  letter-spacing: 0.1em;
}

.how-card-dark .how-num {
  color: #6e6e73;
}

.how-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #fff;
  color: var(--ink);
  display: grid;
  place-items: center;
  margin-bottom: 34px;
}

.how-icon.blue { color: var(--blue); }
.how-icon.teal { color: var(--teal); }

.how-card h3 {
  margin: 0 0 9px;
  font-size: 24px;
  line-height: 1.2;
  letter-spacing: -0.035em;
  font-weight: 600;
}

.how-card p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
  max-width: 290px;
}

.how-mini-tags {
  display: flex;
  gap: 6px;
  margin-top: auto;
  padding-top: 25px;
}

.how-mini-tags span {
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 99px;
  padding: 5px 9px;
  color: #d1d1d6;
  font-size: 9px;
}

.mini-route {
  position: relative;
  height: 70px;
  margin-top: auto;
}

.mini-route::before {
  content: "";
  position: absolute;
  left: 10px;
  right: 16px;
  top: 34px;
  border-top: 2px dashed #b8d9ff;
  transform: rotate(-7deg);
}

.mini-route i {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #fff;
  border: 3px solid var(--blue);
  top: 28px;
}

.mini-route i:nth-child(1) { left: 4px; }
.mini-route i:nth-child(2) { left: 30%; top: 18px; }
.mini-route i:nth-child(3) { left: 60%; top: 30px; }
.mini-route i:nth-child(4) { right: 8px; top: 12px; }

.mini-budget {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 7px 16px;
  margin-top: auto;
  padding-top: 24px;
  border-top: 1px solid var(--line);
  font-size: 10px;
  color: var(--muted);
}

.mini-budget b {
  color: var(--ink);
  font-size: 11px;
  font-weight: 500;
}

/* ------------------------------------------------------------------ */
/* Destinations                                                        */
/* ------------------------------------------------------------------ */
.destinations-section {
  background: var(--bg-soft);
  padding: 100px 0 106px;
}

.destinations-section .section-head {
  margin-bottom: 34px;
}

.destinations-section .section-head p {
  max-width: 220px;
  text-align: right;
  font-size: 13px;
}

.city-grid {
  width: min(1180px, calc(100% - 44px));
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.city-tile {
  position: relative;
  height: 210px;
  border: 0;
  border-radius: 22px;
  padding: 20px;
  text-align: left;
  color: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  isolation: isolate;
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.3s ease;
}

.city-tile::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background:
    radial-gradient(circle at 80% 15%, rgba(255, 255, 255, 0.22), transparent 35%),
    linear-gradient(150deg, rgba(255, 255, 255, 0.12), transparent 55%);
}

.city-tile:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.14);
}

.tone-teal { background: linear-gradient(145deg, #0d5c63, #062f3e); }
.tone-blue { background: linear-gradient(145deg, #1b5f9e, #0b2744); }
.tone-amber { background: linear-gradient(145deg, #9a5b1b, #3e2508); }
.tone-cyan { background: linear-gradient(145deg, #16708a, #083241); }
.tone-slate { background: linear-gradient(145deg, #434852, #15171c); }
.tone-violet { background: linear-gradient(145deg, #5b3c8c, #211634); }
.tone-green { background: linear-gradient(145deg, #2f6d4f, #11291d); }

.city-index {
  position: absolute;
  top: 18px;
  left: 20px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 9px;
  letter-spacing: 0.1em;
}

.city-arrow {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #fff;
  transition: 0.2s ease;
}

.city-tile:hover .city-arrow {
  background: #fff;
  color: var(--ink);
}

.city-name {
  display: block;
  font-size: 29px;
  line-height: 1.1;
  font-weight: 600;
  letter-spacing: -0.05em;
}

.city-tag {
  display: block;
  color: rgba(255, 255, 255, 0.6);
  font-size: 10px;
  margin-top: 5px;
}

.city-line {
  width: 24px;
  height: 2px;
  background: rgba(255, 255, 255, 0.35);
  margin-top: 15px;
}

.city-grid .city-tile:nth-child(5) {
  grid-column: span 2;
}

/* ------------------------------------------------------------------ */
/* Closing & footer                                                    */
/* ------------------------------------------------------------------ */
.closing-section {
  position: relative;
  overflow: hidden;
  background: #000;
  color: #fff;
  padding: 120px 0;
  text-align: center;
}

.closing-glow {
  position: absolute;
  width: 650px;
  height: 420px;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(0, 113, 227, 0.3), rgba(0, 166, 160, 0.12) 40%, transparent 70%);
  filter: blur(50px);
}

.closing-content {
  position: relative;
  z-index: 1;
  width: min(760px, calc(100% - 44px));
  margin: 0 auto;
}

.closing-section .eyebrow {
  color: #6e6e73;
}

.closing-section h2 {
  margin: 18px 0 18px;
  font-size: clamp(48px, 6.2vw, 78px);
  line-height: 1.03;
  letter-spacing: -0.055em;
  font-weight: 600;
}

.closing-section h2 span {
  color: #86868b;
}

.closing-section p {
  margin: 0 0 28px;
  color: #a1a1a6;
  font-size: 16px;
}

.closing-section .btn {
  padding: 13px 24px;
  font-size: 15px;
}

.home-footer {
  background: #f5f5f7;
  padding: 34px 0;
}

.footer-inner {
  width: min(1180px, calc(100% - 44px));
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 30px;
}

.footer-brand span {
  display: block;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.footer-brand small {
  display: block;
  color: var(--faint);
  font-size: 7px;
  letter-spacing: 0.16em;
  margin-top: 2px;
}

.footer-links {
  display: flex;
  gap: 20px;
}

.footer-links a {
  color: var(--muted);
  font-size: 10px;
}

.footer-links a:hover {
  color: var(--ink);
}

.footer-inner p {
  margin: 0 0 0 auto;
  color: var(--faint);
  font-size: 9px;
}

@media (max-width: 1050px) {
  .hero {
    grid-template-columns: 1fr;
    gap: 40px;
    padding: 64px 0 58px;
  }

  .hero-copy {
    max-width: 720px;
  }

  .hero-visual {
    min-height: 500px;
  }

  .visual-card {
    width: min(620px, 94%);
  }

  .planner-grid {
    grid-template-columns: 1fr;
    gap: 26px;
  }

  .form-side {
    padding-left: 0;
    border-left: 0;
    border-top: 1px solid var(--line-soft);
    padding-top: 26px;
  }

  .how-grid {
    grid-template-columns: 1fr 1fr;
  }

  .how-card:last-child {
    grid-column: span 2;
  }

  .city-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .city-grid .city-tile:nth-child(5) {
    grid-column: span 1;
  }
}

@media (max-width: 720px) {
  .hero {
    width: calc(100% - 28px);
    padding-top: 46px;
  }

  .hero h1 {
    font-size: clamp(48px, 14vw, 64px);
  }

  .hero-sub {
    font-size: 17px;
  }

  .hero-actions {
    flex-wrap: wrap;
    gap: 16px;
  }

  .hero-visual {
    min-height: 410px;
  }

  .visual-card {
    transform: none;
    border-radius: 24px;
    padding: 11px;
  }

  .float-budget {
    left: 4px;
    bottom: 30px;
  }

  .float-route {
    right: 4px;
    top: 24px;
  }

  .planner-section,
  .how-section,
  .destinations-section {
    padding: 68px 0;
  }

  .planner-head,
  .planner-card,
  .section-head,
  .how-grid,
  .city-grid {
    width: calc(100% - 28px);
  }

  .planner-card {
    border-radius: 24px;
    padding: 22px 18px 18px;
  }

  .planner-steps {
    grid-template-columns: 1fr;
    gap: 10px;
    padding-bottom: 18px;
  }

  .planner-steps > div {
    display: flex;
    gap: 9px;
  }

  .planner-steps span {
    grid-row: auto;
    width: 26px;
    height: 26px;
  }

  .two-col {
    grid-template-columns: 1fr;
  }

  .duration-row {
    flex-wrap: wrap;
  }

  .duration-result {
    margin-left: 0;
  }

  .form-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .submit-btn {
    width: 100%;
  }

  .form-foot {
    text-align: center;
  }

  .how-grid {
    grid-template-columns: 1fr;
  }

  .how-card:last-child {
    grid-column: auto;
  }

  .section-head,
  .destinations-section .section-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .destinations-section .section-head p {
    text-align: left;
  }

  .city-grid {
    grid-template-columns: 1fr 1fr;
  }

  .city-tile {
    height: 170px;
  }

  .city-grid .city-tile:nth-child(5) {
    grid-column: span 2;
  }

  .city-name {
    font-size: 25px;
  }

  .closing-section {
    padding: 80px 0;
  }

  .closing-section h2 {
    font-size: 40px;
  }

  .footer-inner {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .footer-inner p {
    margin: 0;
  }
}
</style>
