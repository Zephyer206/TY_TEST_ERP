// Complete frontend packaging for the small Windows acceptance host.
// Type checks remain separate; no source modules are excluded from this build.
import { fileURLToPath } from 'node:url'
import { build } from '../frontend/node_modules/vite/dist/node/index.js'

await build({
  root: fileURLToPath(new URL('../frontend/', import.meta.url)),
  configFile: fileURLToPath(new URL('../frontend/vite.config.ts', import.meta.url)),
  build: {
    target: 'esnext',
    minify: false,
    reportCompressedSize: false,
    rollupOptions: { maxParallelFileOps: 4 },
  },
})
