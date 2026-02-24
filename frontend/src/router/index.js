import { createRouter, createWebHistory } from 'vue-router'
import Home from '../components/Home/Home.vue'
import Prompt from '../components/Prompt/Prompt.vue'

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
]

const router = createRouter({
  history: createWebHistory("/eva-vr/"),
  routes,
})

export default router