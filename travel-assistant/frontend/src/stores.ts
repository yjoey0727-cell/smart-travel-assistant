import { defineStore } from 'pinia'
import type { SessionInfo, Trip } from './types'
import { api } from './api'

export const useSessionStore = defineStore('session', {
  state: () => ({
    info: null as SessionInfo | null,
    loading: false,
  }),
  actions: {
    async ensure() {
      if (this.info || this.loading) return
      this.loading = true
      try {
        this.info = await api.session()
      } finally {
        this.loading = false
      }
    },
  },
})

export const useTripStore = defineStore('trip', {
  state: () => ({
    trip: null as Trip | null,
    loading: false,
    saving: false,
    selectedDay: 1,
    selectedItemId: '' as string,
    toast: { message: '', kind: 'info' as 'info' | 'success' | 'error', visible: false },
    toastTimer: 0 as number,
  }),
  getters: {
    currentDay(state) {
      return state.trip?.days.find((d) => d.dayIndex === state.selectedDay) || state.trip?.days[0] || null
    },
    dayRoutes(state) {
      return (state.trip?.routes || []).filter((r) => r.dayIndex === state.selectedDay)
    },
    isDemo(state) {
      return state.trip?.meta?.demo ?? true
    },
  },
  actions: {
    async load(tripId: string) {
      this.loading = true
      try {
        const loaded = await api.getTrip(tripId)
        this.trip = loaded
        if (!loaded.days.some((d) => d.dayIndex === this.selectedDay)) {
          this.selectedDay = loaded.days[0]?.dayIndex || 1
        }
      } finally {
        this.loading = false
      }
    },
    apply(trip: Trip) {
      this.trip = trip
      if (!trip.days.some((d) => d.dayIndex === this.selectedDay)) {
        this.selectedDay = trip.days[0]?.dayIndex || 1
      }
      if (this.selectedItemId && !trip.days.some((d) => d.items.some((i) => i.id === this.selectedItemId))) {
        this.selectedItemId = ''
      }
    },
    selectDay(dayIndex: number) {
      this.selectedDay = dayIndex
      this.selectedItemId = ''
    },
    selectItem(itemId: string) {
      this.selectedItemId = itemId
    },
    notify(message: string, kind: 'info' | 'success' | 'error' = 'info') {
      this.toast = { message, kind, visible: true }
      window.clearTimeout(this.toastTimer)
      this.toastTimer = window.setTimeout(() => {
        this.toast.visible = false
      }, 3200)
    },
    async addItem(dayIndex: number, poi: any, afterItemId?: string) {
      if (!this.trip || this.saving) return
      this.saving = true
      try {
        const trip = await api.addItem(this.trip.id, dayIndex, poi, afterItemId)
        this.apply(trip)
        this.notify('已添加，路线与预算已更新', 'success')
      } catch (error: any) {
        this.notify(error.message || '添加失败', 'error')
      } finally {
        this.saving = false
      }
    },
    async removeItem(itemId: string) {
      if (!this.trip || this.saving) return
      this.saving = true
      try {
        const trip = await api.deleteItem(this.trip.id, itemId)
        this.apply(trip)
        this.notify('已删除，路线与预算已更新', 'success')
      } catch (error: any) {
        this.notify(error.message || '删除失败', 'error')
      } finally {
        this.saving = false
      }
    },
    async reorder(dayIndex: number, itemIds: string[]) {
      if (!this.trip || this.saving) return
      this.saving = true
      try {
        const trip = await api.reorderDay(this.trip.id, dayIndex, itemIds)
        this.apply(trip)
        this.notify('顺序已调整', 'success')
      } catch (error: any) {
        this.notify(error.message || '调整失败', 'error')
      } finally {
        this.saving = false
      }
    },
    async toggleLock(itemId: string, locked: boolean) {
      if (!this.trip) return
      this.saving = true
      try {
        const trip = await api.updateItem(this.trip.id, itemId, { locked })
        this.apply(trip)
      } catch (error: any) {
        this.notify(error.message || '更新失败', 'error')
      } finally {
        this.saving = false
      }
    },
  },
})
