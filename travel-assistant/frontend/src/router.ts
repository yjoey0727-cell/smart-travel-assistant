import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import PlanView from './views/PlanView.vue'
import TripView from './views/TripView.vue'
import TripsView from './views/TripsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/plan/:runId', name: 'plan', component: PlanView },
    { path: '/trips', name: 'trips', component: TripsView },
    { path: '/trips/:tripId', name: 'trip', component: TripView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
