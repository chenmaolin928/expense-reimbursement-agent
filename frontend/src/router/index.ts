import { createRouter, createWebHashHistory } from 'vue-router'

const devMode = import.meta.env.DEV || new URLSearchParams(window.location.search).has('dev')

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/ChatView.vue'),
  },
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    children: [
      { path: '', redirect: '/admin/knowledge' },
      { path: 'knowledge', component: () => import('../views/admin/KnowledgeView.vue') },
      { path: 'policy', component: () => import('../views/admin/PolicyView.vue') },
      { path: 'policy/review/:policyId/:versionId', component: () => import('../views/admin/PolicyReviewView.vue') },
      { path: 'analytics', component: () => import('../views/admin/AnalyticsView.vue') },
      ...(devMode
        ? [{ path: 'debug', component: () => import('../views/admin/DevDebugView.vue') }]
        : []),
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
})
