/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'vue-toastification' {
  import type { Plugin } from 'vue'
  export const POSITION: {
    TOP_LEFT: string
    TOP_CENTER: string
    TOP_RIGHT: string
    BOTTOM_LEFT: string
    BOTTOM_CENTER: string
    BOTTOM_RIGHT: string
  }
  export interface PluginOptions {
    position?: string
    timeout?: number
    closeOnClick?: boolean
    pauseOnFocusLoss?: boolean
    pauseOnHover?: boolean
    draggable?: boolean
    showCloseButtonOnHover?: boolean
    hideProgressBar?: boolean
    closeButton?: string | boolean
    icon?: boolean
    rtl?: boolean
    maxToasts?: number
  }
  export function useToast(): {
    success: (message: string) => void
    error: (message: string) => void
    warning: (message: string) => void
    info: (message: string) => void
  }
  const Toast: Plugin
  export default Toast
}
