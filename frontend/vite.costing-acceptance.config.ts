import { mergeConfig } from 'vite'
import base from './vite.config'
export default mergeConfig(base, {server:{host:'127.0.0.1',port:5186,strictPort:true,proxy:{
  '/api':{target:'http://127.0.0.1:8016',changeOrigin:true},
  '/static':{target:'http://127.0.0.1:8016',changeOrigin:true},
}}})
