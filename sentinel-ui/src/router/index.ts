import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { layout: 'blank', requiresAuth: false, title: 'Login' },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true, title: 'Dashboard' },
  },
  {
    path: '/services',
    name: 'Services',
    component: () => import('@/views/ServicesView.vue'),
    meta: { requiresAuth: true, title: 'Services' },
  },
  {
    path: '/services/:name',
    name: 'ServiceDetail',
    component: () => import('@/views/ServiceDetailView.vue'),
    meta: { requiresAuth: true, title: 'Service Detail' },
  },
  {
    path: '/deployments',
    name: 'Deployments',
    component: () => import('@/views/DeploymentsView.vue'),
    meta: { requiresAuth: true, title: 'Deployments' },
  },
  {
    path: '/projects',
    name: 'Projects',
    component: () => import('@/views/ProjectsView.vue'),
    meta: { requiresAuth: true, title: 'Projects' },
  },
  {
    path: '/projects/new',
    name: 'NewProject',
    component: () => import('@/views/NewProjectView.vue'),
    meta: { requiresAuth: true, title: 'New Project' },
  },
  {
    path: '/projects/deploy-wizard',
    name: 'DeployWizard',
    component: () => import('@/views/DeployWizardView.vue'),
    meta: { requiresAuth: true, title: 'Deploy Wizard' },
  },
  {
    path: '/projects/:id',
    name: 'ProjectDetail',
    component: () => import('@/views/ProjectDetailView.vue'),
    meta: { requiresAuth: true, title: 'Project Detail' },
  },
  {
    path: '/database',
    name: 'Database',
    component: () => import('@/views/DatabaseView.vue'),
    meta: { requiresAuth: true, title: 'Database' },
  },
  {
    path: '/domains',
    name: 'Domains',
    component: () => import('@/views/DomainsView.vue'),
    meta: { requiresAuth: true, title: 'Domains' },
  },
  {
    path: '/custom-domains',
    name: 'CustomDomains',
    component: () => import('@/views/CustomDomainsView.vue'),
    meta: { requiresAuth: true, title: 'Custom Domains' },
  },
  {
    path: '/security',
    name: 'Security',
    component: () => import('@/views/SecurityView.vue'),
    meta: { requiresAuth: true, title: 'Security' },
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('@/views/LogsView.vue'),
    meta: { requiresAuth: true, title: 'Logs' },
  },
  {
    path: '/system',
    name: 'System',
    component: () => import('@/views/SystemView.vue'),
    meta: { requiresAuth: true, title: 'System' },
  },
  {
    path: '/audit',
    name: 'Audit',
    component: () => import('@/views/AuditView.vue'),
    meta: { requiresAuth: true, title: 'Audit' },
  },
  {
    path: '/docs',
    name: 'Docs',
    component: () => import('@/views/DocsView.vue'),
    meta: { requiresAuth: true, title: 'Deploy Guide' },
  },
  {
    path: '/setup',
    name: 'Setup',
    component: () => import('@/views/SetupView.vue'),
    meta: { layout: 'blank', requiresAuth: true, title: 'Setup' },
  },
  {
    path: '/public/docs',
    component: () => import('@/components/docs/DocsLayout.vue'),
    meta: { layout: 'blank', requiresAuth: false },
    children: [
      { path: '', name: 'DocsOverview', component: () => import('@/views/docs/OverviewView.vue'), meta: { layout: 'blank', requiresAuth: false, title: 'Sentinel Docs' } },
      { path: 'deploy-guide', name: 'DocsDeployGuide', component: () => import('@/views/docs/DeployGuideView.vue'), meta: { layout: 'blank', requiresAuth: false, title: 'Deploy Guide - Sentinel Docs' } },
      { path: 'cli', name: 'DocsCli', component: () => import('@/views/docs/CliView.vue'), meta: { layout: 'blank', requiresAuth: false, title: 'CLI - Sentinel Docs' } },
      { path: 'mcp', name: 'DocsMcp', component: () => import('@/views/docs/McpView.vue'), meta: { layout: 'blank', requiresAuth: false, title: 'MCP Server - Sentinel Docs' } },
      { path: 'custom-domains', name: 'DocsCustomDomains', component: () => import('@/views/docs/CustomDomainsView.vue'), meta: { layout: 'blank', requiresAuth: false, title: 'Custom Domains - Sentinel Docs' } },
      { path: 'api', name: 'DocsApi', component: () => import('@/views/docs/ApiReferenceView.vue'), meta: { layout: 'blank', requiresAuth: false, title: 'API Reference - Sentinel Docs' } },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { layout: 'blank', requiresAuth: false, title: '404 Not Found' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

function decodeJwt(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded)
  } catch {
    return null
  }
}

// Auth + setup-wizard guard
router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('sentinel_admin_token')
  let isAuthenticated = false

  if (token) {
    const payload = decodeJwt(token)
    const isExpired = payload?.exp ? Date.now() >= (payload.exp as number) * 1000 : true
    isAuthenticated = !isExpired && payload?.is_admin === true
  }

  if (to.meta.requiresAuth && !isAuthenticated) {
    return next('/login')
  }
  if (to.path === '/login' && isAuthenticated) {
    return next('/')
  }

  // Setup wizard redirect: authed + setup incomplete + not going to /setup
  if (isAuthenticated && to.path !== '/setup' && to.path !== '/login') {
    try {
      const { useSetupStore } = await import('@/stores/setup')
      const store = useSetupStore()
      if (store.isSetupComplete === null) {
        await store.fetchStatus()
      }
      if (store.isSetupComplete === false) {
        return next('/setup')
      }
    } catch {
      // If setup status is unreachable, don't block navigation
    }
  }

  next()
})

// Dynamic document title
router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} - Sentinel` : 'Sentinel'
})

export default router
