import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

// 顺序很重要：先引组件库默认样式，再用项目主题覆盖变量
import 'element-plus/dist/index.css'
import '@/styles/theme.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// token 过期由 axios 拦截器触发该事件，统一回到登录页
window.addEventListener('auth:expired', () => {
  if (router.currentRoute.value.name !== 'login') {
    router.replace({ name: 'login' })
  }
})

app.mount('#app')
