import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/views/AppLayout.vue'
import Home from '@/views/Home.vue'
import ProductDetail from '@/views/ProductDetail.vue'
import ProductBoms from '@/views/ProductBoms.vue'
import ProductBomDetail from '@/views/ProductBomDetail.vue'
import ProductBomOverview from '@/views/ProductBomOverview.vue'
import ManualReview from '@/views/ManualReview.vue'
import ProductManual from '@/views/ProductManual.vue'
import PosterCanvasEditor from '@/views/PosterCanvasEditor.vue'
import PromptPlaybook from '@/views/PromptPlaybook.vue'
import Admin from '@/views/Admin.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Home',
        component: Home,
        meta: { moduleKey: 'home' }
      },
      {
        path: 'product/:id/boms',
        name: 'ProductBoms',
        component: ProductBoms,
        meta: { moduleKey: 'kbSearch' }
      },
      {
        path: 'product/:id/overview',
        name: 'ProductBomOverview',
        component: ProductBomOverview,
        meta: { moduleKey: 'kbSearch' }
      },
      {
        path: 'product/:id/boms/:bom',
        name: 'ProductBomDetail',
        component: ProductBomDetail,
        meta: { moduleKey: 'kbSearch' }
      },
      {
        path: 'product/:id',
        name: 'ProductDetail',
        component: ProductDetail,
        meta: { moduleKey: 'kbSearch' }
      },
      {
        path: 'manual/review',
        name: 'ManualReview',
        component: ManualReview,
        meta: { moduleKey: 'manual' }
      },
      {
        path: 'manual/manual-detail',
        name: 'ProductManual',
        component: ProductManual,
        meta: { moduleKey: 'export' }
      },
      {
        path: 'prompt-playbook',
        name: 'PromptPlaybook',
        component: PromptPlaybook,
        meta: { moduleKey: 'kbSearch' }
      },
      {
        path: 'admin',
        name: 'Admin',
        component: Admin,
        meta: { moduleKey: 'admin' }
      },
      {
        path: 'poster-editor',
        name: 'PosterCanvasEditor',
        component: PosterCanvasEditor,
        meta: { moduleKey: 'export' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router