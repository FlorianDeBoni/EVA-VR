import { createRouter, createWebHistory } from 'vue-router'
import Home from '../components/Home.vue'
import Test from '../components/Test.vue'

const routes = [
  { 
    path: '/',
    component: Home,
    name: 'Home',
  },
  { path: '/test',
    component: Test,
    name: 'Test', 
  },
]

const router = createRouter({
  history: createWebHistory("/eva-vr/"),
  routes,
})

export default router