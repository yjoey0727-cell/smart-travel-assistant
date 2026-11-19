/// <reference types="vite/client" />

interface Window {
  AMap?: any
  _AMapSecurityConfig?: { securityJsCode?: string; serviceHost?: string }
}

interface ImportMetaEnv {
  readonly VITE_AMAP_KEY?: string
  readonly VITE_AMAP_SECURITY_CODE?: string
}
