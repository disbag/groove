import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Относительный base: сайт работает и на disbag.github.io/groove/, и локально.
export default defineConfig({
  base: './',
  plugins: [vue()],
})
