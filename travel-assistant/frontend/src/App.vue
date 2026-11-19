<script setup lang="ts">
import { onMounted } from 'vue'
import { useSessionStore } from './stores'

const session = useSessionStore()
onMounted(() => {
  session.ensure().catch(() => undefined)
})
</script>

<template>
  <router-view />
</template>
