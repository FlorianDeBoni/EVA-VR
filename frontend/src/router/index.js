import { createRouter, createWebHistory } from 'vue-router'
import Home from '../components/Home/Home.vue'
import Prompt from '../components/Prompt/Prompt.vue'
import EditingHome from '@/components/Editing/EditingHome.vue'

const routes = [
  { 
    path: '/',
    component: Home,
    name: 'Home',
  },
  { path: '/prompt',
    component: Prompt,
    name: 'Prompt', 
  },
  {
    path: '/editing',
    component: EditingHome,
    name: 'Editing',
  }
]

const router = createRouter({
  history: createWebHistory("/eva-vr/"),
  routes,
})

export default router