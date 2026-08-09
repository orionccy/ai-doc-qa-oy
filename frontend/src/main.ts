import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'

// 应用入口:注册 Pinia(状态管理)+ Router(路由)
createApp(App).use(createPinia()).use(router).mount('#app')
