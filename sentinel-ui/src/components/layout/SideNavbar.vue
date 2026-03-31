<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import {
  LayoutDashboard,
  Container,
  Rocket,
  FolderGit2,
  Database,
  Globe,
  ScrollText,
  Activity,
  ClipboardList,
  Sun,
  Moon,
  LogOut,
  ChevronLeft,
  User,
} from 'lucide-vue-next'

interface Props {
  collapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  collapsed: false,
})

const emit = defineEmits<{
  toggleCollapse: []
}>()

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Services', path: '/services', icon: Container },
  { name: 'Deployments', path: '/deployments', icon: Rocket },
  { name: 'Projects', path: '/projects', icon: FolderGit2 },
  { name: 'Database', path: '/database', icon: Database },
  { name: 'Domains', path: '/domains', icon: Globe },
  { name: 'Logs', path: '/logs', icon: ScrollText },
  { name: 'System', path: '/system', icon: Activity },
  { name: 'Audit', path: '/audit', icon: ClipboardList },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

function navigate(path: string) {
  router.push(path)
}

const userName = computed(() => authStore.user?.username ?? 'User')
const userRole = computed(() => authStore.user?.role ?? 'admin')

function handleLogout() {
  authStore.logout()
}
</script>

<template>
  <aside
    :class="[
      'flex flex-col h-full bg-white dark:bg-neutral-950 border-r border-kPrimary/10 dark:border-neutral-800 transition-all duration-300',
      props.collapsed ? 'w-16' : 'w-60',
    ]"
  >
    <!-- Logo -->
    <div class="flex items-center gap-3 px-4 h-16 border-b border-kPrimary/10 dark:border-neutral-800 shrink-0">
      <div class="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
        <Activity class="w-4 h-4 text-white" />
      </div>
      <Transition
        enter-active-class="transition-opacity duration-200"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-150"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <span v-if="!props.collapsed" class="font-heading font-semibold text-lg text-kPrimary dark:text-white">
          Sentinel
        </span>
      </Transition>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto py-3 px-2 custom-scrollbar">
      <ul class="space-y-0.5">
        <li v-for="item in navItems" :key="item.path">
          <button
            :class="[
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 relative',
              isActive(item.path)
                ? 'bg-accent/10 text-accent dark:text-accent'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-neutral-800/60 hover:text-kPrimary dark:hover:text-white',
            ]"
            @click="navigate(item.path)"
          >
            <!-- Active indicator -->
            <div
              v-if="isActive(item.path)"
              class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-r-full"
            />
            <component :is="item.icon" class="w-[18px] h-[18px] shrink-0" />
            <Transition
              enter-active-class="transition-opacity duration-200"
              enter-from-class="opacity-0"
              enter-to-class="opacity-100"
              leave-active-class="transition-opacity duration-150"
              leave-from-class="opacity-100"
              leave-to-class="opacity-0"
            >
              <span v-if="!props.collapsed" class="truncate">{{ item.name }}</span>
            </Transition>
          </button>
        </li>
      </ul>
    </nav>

    <!-- Divider -->
    <div class="mx-3 border-t border-kPrimary/10 dark:border-neutral-800" />

    <!-- Bottom section -->
    <div class="p-2 space-y-1 shrink-0">
      <!-- Theme toggle -->
      <button
        class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-neutral-800/60 hover:text-kPrimary dark:hover:text-white transition-all duration-200"
        @click="themeStore.toggle()"
      >
        <Moon v-if="!themeStore.isDark" class="w-[18px] h-[18px] shrink-0" />
        <Sun v-else class="w-[18px] h-[18px] shrink-0" />
        <span v-if="!props.collapsed" class="truncate">
          {{ themeStore.isDark ? 'Light Mode' : 'Dark Mode' }}
        </span>
      </button>

      <!-- Collapse toggle (desktop only) -->
      <button
        class="w-full hidden lg:flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-neutral-800/60 hover:text-kPrimary dark:hover:text-white transition-all duration-200"
        @click="emit('toggleCollapse')"
      >
        <ChevronLeft
          :class="[
            'w-[18px] h-[18px] shrink-0 transition-transform duration-200',
            props.collapsed ? 'rotate-180' : '',
          ]"
        />
        <span v-if="!props.collapsed" class="truncate">Collapse</span>
      </button>

      <!-- User info + Logout -->
      <div class="flex items-center gap-3 px-3 py-2.5">
        <div class="w-7 h-7 rounded-full bg-kPrimary/10 dark:bg-neutral-800 flex items-center justify-center shrink-0">
          <User class="w-3.5 h-3.5 text-kPrimary dark:text-gray-400" />
        </div>
        <div v-if="!props.collapsed" class="flex-1 min-w-0">
          <p class="text-sm font-medium text-kPrimary dark:text-white truncate">
            {{ userName }}
          </p>
          <p class="text-2xs text-gray-400 truncate">{{ userRole }}</p>
        </div>
        <button
          v-if="!props.collapsed"
          class="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors shrink-0"
          title="Logout"
          @click="handleLogout"
        >
          <LogOut class="w-4 h-4" />
        </button>
      </div>
    </div>
  </aside>
</template>
