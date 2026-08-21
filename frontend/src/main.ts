import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import VxeUITable from 'vxe-table'
import VxeUIBase from 'vxe-pc-ui'
import 'vxe-table/lib/style.css'
import 'vxe-pc-ui/lib/style.css'

import App from './App.vue'
import router from './router'
import i18n from './locales'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.use(VxeUIBase)
app.use(VxeUITable)
app.use(i18n)

app.mount('#app')
