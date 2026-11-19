export type ItemType = 'attraction' | 'meal' | 'hotel' | 'transit'
export type Pace = 'relaxed' | 'balanced' | 'packed'
export type HotelLevel = 'budget' | 'comfort' | 'premium'
export type RouteMode = 'walking' | 'transit' | 'driving'

export interface GeoPoint {
  lng: number
  lat: number
}

export interface TripItem {
  id: string
  type: ItemType
  title: string
  poiId: string
  location: GeoPoint
  address: string
  startTime: string
  endTime: string
  durationMin: number
  cost: {
    amountCents: number
    currency: string
    category: string
    basis: string
    source: string
    confidence: string
    note?: string
  }
  notes: string
  locked: boolean
  rating: number
  tags: string[]
  image?: string | null
  description?: string
  bookingUrl?: string | null
  area?: string
}

export interface DayPlan {
  dayIndex: number
  date: string
  theme: string
  summary: string
  items: TripItem[]
}

export interface RouteLeg {
  dayIndex: number
  fromItemId: string
  toItemId: string
  mode: RouteMode
  distanceM: number
  durationMin: number
  polyline: number[][]
  status: string
  provider: string
  costCents: number
}

export interface BudgetCategory {
  key: string
  label: string
  amountCents: number
  note?: string
}

export interface BudgetSummary {
  totalCents: number
  perPersonCents: number
  currency: string
  bufferRate: number
  budgetLimitCents: number
  overBudget: boolean
  categories: BudgetCategory[]
  daily: { dayIndex: number; amountCents: number }[]
  transport: {
    amountCents: number
    mode?: string | null
    distanceKm: number
    note: string
    bookingUrl: string
  }
  priceNote: string
  roomCount: number
  headcount: number
}

export interface TripMeta {
  planner: string
  rationale: string
  origin?: string | null
  originCenter?: GeoPoint | null
  transport: { intercity?: string; local?: string }
  travelers: { adults: number; children: number }
  preferences: {
    scenery: string[]
    food: string[]
    pace: Pace
    hotelLevel: HotelLevel
    avoid: string[]
  }
  budgetLimitCents: number
  hotelLevel: HotelLevel
  notes?: string | null
  generatedAt: string
  demo: boolean
  amap: boolean
  llm: boolean
  dayCount: number
  candidateSource?: string
  candidateCounts?: Record<string, number>
}

export interface Trip {
  id: string
  version: number
  title: string
  destination: {
    city: string
    adcode?: string | null
    center: GeoPoint
  }
  startDate: string
  endDate: string
  days: DayPlan[]
  routes: RouteLeg[]
  budget: BudgetSummary
  meta: TripMeta
  createdAt: string
  updatedAt: string
}

export interface Poi {
  poiId: string
  name: string
  type: 'attraction' | 'meal' | 'hotel'
  address: string
  lng: number
  lat: number
  rating: number
  costCents: number
  costBasis: 'ticket' | 'person' | 'room_night'
  durationMin: number
  tags: string[]
  image?: string | null
  description?: string
  source: string
  confidence: string
  bookingUrl?: string | null
  area?: string | null
}

export interface SessionInfo {
  sessionId: string
  demoMode: boolean
  amapConfigured: boolean
  llmConfigured: boolean
  demoCity: string
  exportReady: boolean
}

export interface PlanPayload {
  destination: { city: string; adcode?: string }
  origin?: string
  startDate: string
  endDate: string
  travelers: { adults: number; children: number }
  budget: { totalCents: number; currency: string; level: HotelLevel }
  preferences: {
    scenery: string[]
    food: string[]
    pace: Pace
    hotelLevel: HotelLevel
    avoid: string[]
  }
  transport: { intercity: 'auto' | 'rail' | 'flight'; local: 'public' | 'taxi' | 'mixed' }
  notes?: string
}

export interface TripSummary {
  id: string
  title: string
  city: string
  startDate: string
  endDate: string
  days: number
  totalCents: number
  cover?: string | null
  updatedAt?: string | null
  version: number
}

export type PlanEvent =
  | { type: 'stage'; stage: string; progress: number; message: string; id?: number }
  | { type: 'day'; days: DayPlan[]; id?: number }
  | { type: 'plan'; tripId: string; version: number; title: string; demo: boolean; planner: string; id?: number }
  | { type: 'done'; demo?: boolean; planner?: string; id?: number }
  | { type: 'error'; message: string; id?: number }
