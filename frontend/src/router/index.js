import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import ProductDetail from '@/views/ProductDetail.vue'
import ProductBoms from '@/views/ProductBoms.vue'
import ProductBomDetail from '@/views/ProductBomDetail.vue'
import ProductBomOverview from '@/views/ProductBomOverview.vue'
import ManualReview from '@/views/ManualReview.vue'
import ProductManual from '@/views/ProductManual.vue'
import PosterCanvasEditor from '@/views/PosterCanvasEditor.vue'
import PromptPlaybook from '@/views/PromptPlaybook.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/product/:id/boms',
    name: 'ProductBoms',
    component: ProductBoms
  },
  {
    path: '/product/:id/overview',
    name: 'ProductBomOverview',
    component: ProductBomOverview
  },
  {
    path: '/product/:id/boms/:bom',
    name: 'ProductBomDetail',
    component: ProductBomDetail
  },
  {
    path: '/product/:id',
    name: 'ProductDetail',
    component: ProductDetail
  },
  {
    path: '/manual/review',
    name: 'ManualReview',
    component: ManualReview
  },
  {
    path: '/manual/manual-detail',
    name: 'ProductManual',
    component: ProductManual
  },
  {
    path: '/prompt-playbook',
    name: 'PromptPlaybook',
    component: PromptPlaybook
  },
  {
    path: '/poster-editor',
    name: 'PosterCanvasEditor',
    component: PosterCanvasEditor
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router