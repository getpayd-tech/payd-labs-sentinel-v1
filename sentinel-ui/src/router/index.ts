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

// Auth guard
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const isAuthenticated = !!token

  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

// Dynamic document title
router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} — Sentinel` : 'Sentinel'
})

export default router
