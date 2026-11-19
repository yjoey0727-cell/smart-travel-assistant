<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 16 })

const paths: Record<string, string> = {
  sparkles: 'M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3zM19 14l.9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14zM5 14l.7 1.8L7.5 16.5l-1.8.7L5 19l-.7-1.8L2.5 16.5l1.8-.7L5 14z',
  pin: 'M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1116 0zM12 13a3 3 0 100-6 3 3 0 000 6z',
  calendar: 'M8 2v3M16 2v3M3.5 9h17M5 4.5h14a1.5 1.5 0 011.5 1.5v14A1.5 1.5 0 0119 21.5H5A1.5 1.5 0 013.5 20V6A1.5 1.5 0 015 4.5z',
  users: 'M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75',
  wallet: 'M3 7.5A2.5 2.5 0 015.5 5H19a2 2 0 012 2v11a2 2 0 01-2 2H5.5A2.5 2.5 0 013 17.5v-10zM3 8h18M16 13h2',
  plus: 'M12 5v14M5 12h14',
  trash: 'M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5',
  'arrow-up': 'M12 19V5M5 12l7-7 7 7',
  'arrow-down': 'M12 5v14M5 12l7 7 7-7',
  lock: 'M6 10V8a6 6 0 1112 0v2M5 10h14v10H5V10zM12 14v2',
  unlock: 'M6 10V8a6 6 0 0111.3-2.8M5 10h14v10H5V10zM12 14v2',
  download: 'M12 3v12M7 10l5 5 5-5M4 20h16',
  search: 'M21 21l-4.35-4.35M19 11a8 8 0 11-16 0 8 8 0 0116 0z',
  clock: 'M12 22a10 10 0 100-20 10 10 0 000 20zM12 6v6l4 2',
  'arrow-left': 'M19 12H5M12 19l-7-7 7-7',
  'arrow-right': 'M5 12h14M12 5l7 7-7 7',
  x: 'M18 6L6 18M6 6l12 12',
  route: 'M4 19a2 2 0 100-4 2 2 0 000 4zM20 5a2 2 0 100-4 2 2 0 000 4zM6 15V9a3 3 0 013-3h6M18 9v6a3 3 0 01-3 3H9',
  meal: 'M4 3v8a2 2 0 002 2h0a2 2 0 002-2V3M6 13v8M18 3c-2 2-2 5-2 7 0 2 1 3 2 3s2-1 2-3c0-2 0-5-2-7zM18 13v8',
  hotel: 'M2 20V8M2 12h20v8M22 20V12a4 4 0 00-4-4h-7v4M6 12a2 2 0 100-4 2 2 0 000 4z',
  attraction: 'M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6M9 10h.01M15 10h.01',
  external: 'M14 3h7v7M10 14L21 3M21 14v5a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h5',
  check: 'M20 6L9 17l-5-5',
  refresh: 'M21 12a9 9 0 01-15.5 6.2M3 12a9 9 0 0115.5-6.2M3 4v4h4M21 20v-4h-4',
  menu: 'M4 6h16M4 12h16M4 18h16',
  'chevron-right': 'M9 18l6-6-6-6',
  'chevron-down': 'M6 9l6 6 6-6',
  copy: 'M8 8V5a2 2 0 012-2h9a2 2 0 012 2v9a2 2 0 01-2 2h-3M5 8h9a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2v-9a2 2 0 012-2z',
  info: 'M12 22a10 10 0 100-20 10 10 0 000 20zM12 16v-4M12 8h.01',
  compass: 'M12 22a10 10 0 100-20 10 10 0 000 20zM16.2 7.8l-2.1 6.3-6.3 2.1 2.1-6.3 6.3-2.1z',
}
</script>

<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.info" />
  </svg>
</template>
