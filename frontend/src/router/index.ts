import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/pages/LoginPage.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      redirect: '/chat',
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/pages/ChatPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/tasks',
      name: 'my-tasks',
      component: () => import('@/pages/MyTasksPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/help/knowledge',
      name: 'knowledge-help',
      component: () => import('@/pages/KnowledgeHelpPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/oa/travel/:taskId',
      name: 'oa-travel-apply',
      component: () => import('@/pages/OaTravelApplyPage.vue'),
      meta: { requiresAuth: true, standalone: true },
    },
    {
      path: '/settings',
      component: () => import('@/pages/settings/SettingsLayout.vue'),
      meta: { requiresAuth: true },
      redirect: '/settings/account',
      children: [
        {
          path: 'theme',
          name: 'settings-theme',
          component: () => import('@/pages/settings/ThemeSettingsPage.vue'),
        },
        {
          path: 'account',
          name: 'settings-account',
          component: () => import('@/pages/settings/AccountSettingsPage.vue'),
        },
        {
          path: 'version',
          name: 'settings-version',
          component: () => import('@/pages/settings/VersionSettingsPage.vue'),
        },
        {
          path: 'memory',
          name: 'settings-memory',
          component: () => import('@/pages/settings/MemorySettingsPage.vue'),
        },
      ],
    },
    {
      path: '/admin',
      component: () => import('@/pages/admin/AdminLayout.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
      redirect: '/admin/knowledge',
      children: [
        {
          path: 'knowledge',
          name: 'admin-knowledge',
          component: () => import('@/pages/admin/KnowledgeManagePage.vue'),
        },
        {
          path: 'conversations',
          name: 'admin-conversations',
          component: () => import('@/pages/admin/ConversationsMonitorPage.vue'),
        },
        {
          path: 'settings',
          name: 'admin-settings',
          component: () => import('@/pages/admin/SystemSettingsPage.vue'),
        },
        {
          path: 'project-mapping',
          name: 'admin-project-mapping',
          component: () => import('@/pages/admin/ProjectMappingPage.vue'),
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (auth.token && !auth.user) {
    await auth.restoreSession()
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'chat' }
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'chat' }
  }

  return true
})

export default router
