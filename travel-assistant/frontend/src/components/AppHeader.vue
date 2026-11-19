<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useSessionStore } from '../stores'
import AppIcon from './AppIcon.vue'

const route = useRoute()
const session = useSessionStore()
const isHome = computed(() => route.name === 'home')
</script>

<template>
  <header class="app-header">
    <div class="nav-inner">
      <RouterLink to="/" class="brand" aria-label="漫游首页">
        <span class="brand-word">漫游</span>
        <span class="brand-mark"><AppIcon name="compass" :size="12" /></span>
      </RouterLink>

      <nav class="nav">
        <RouterLink to="/" :class="{ active: isHome }">开始规划</RouterLink>
        <RouterLink to="/trips" :class="{ active: route.name === 'trips' }">我的行程</RouterLink>
      </nav>

      <div class="nav-right">
        <span v-if="session.info" class="status" :class="{ demo: session.info.demoMode }">
          <span class="status-dot"></span>
          {{ session.info.demoMode ? '演示模式' : '高德 · AI 在线' }}
        </span>
        <RouterLink to="/" class="nav-cta">开始规划</RouterLink>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(251, 251, 253, 0.78);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.nav-inner {
  width: min(1180px, calc(100% - 44px));
  margin: 0 auto;
  height: 50px;
  display: flex;
  align-items: center;
  gap: 38px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--ink);
  flex-shrink: 0;
}

.brand-word {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.brand-mark {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--ink);
  color: #fff;
  display: grid;
  place-items: center;
  transform: translateY(1px);
}

.nav {
  display: flex;
  align-items: center;
  gap: 28px;
  flex: 1;
}

.nav a {
  color: rgba(29, 29, 31, 0.72);
  font-size: 12px;
  line-height: 1;
  letter-spacing: -0.01em;
  transition: color 0.2s ease;
}

.nav a:hover,
.nav a.active {
  color: var(--ink);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--faint);
  font-size: 10px;
  letter-spacing: 0.01em;
}

.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #30d158;
  box-shadow: 0 0 0 2px rgba(48, 209, 88, 0.12);
}

.status.demo .status-dot {
  background: #ff9f0a;
  box-shadow: 0 0 0 2px rgba(255, 159, 10, 0.12);
}

.nav-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--blue);
  color: #fff;
  border-radius: 980px;
  padding: 7px 14px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  transition: 0.2s ease;
}

.nav-cta:hover {
  background: var(--blue-hover);
  color: #fff;
}

@media (max-width: 720px) {
  .nav-inner {
    width: calc(100% - 28px);
    height: 46px;
    gap: 18px;
  }

  .nav {
    gap: 16px;
    justify-content: flex-end;
  }

  .nav a {
    font-size: 11px;
  }

  .status {
    display: none;
  }

  .nav-cta {
    display: none;
  }
}
</style>
