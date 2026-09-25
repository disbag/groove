<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import SearchBox from './components/SearchBox.vue'
import { getMeta } from './api.js'
import { favoritesCount } from './favorites.js'
import { formatDate } from './format.js'

const meta = ref(null)
onMounted(async () => {
  try {
    meta.value = await getMeta()
  } catch {
    meta.value = null
  }
})
</script>

<template>
  <header class="site-header">
    <div class="container header-row">
      <RouterLink to="/" class="logo" aria-label="Groove — на главную">
        <svg viewBox="0 0 64 64" width="28" height="28" aria-hidden="true">
          <circle cx="32" cy="32" r="30" fill="currentColor" />
          <circle cx="32" cy="32" r="22" fill="none" stroke="var(--groove)" stroke-width="1.5" />
          <circle cx="32" cy="32" r="16" fill="none" stroke="var(--groove)" stroke-width="1.5" />
          <circle cx="32" cy="32" r="10" fill="var(--accent)" />
          <circle cx="32" cy="32" r="2.2" fill="currentColor" />
        </svg>
        <span>Groove<span class="logo-muted"> · цены на винил</span></span>
      </RouterLink>
      <SearchBox class="header-search" />
      <nav class="header-nav">
        <RouterLink to="/favorites" class="nav-link">
          Избранное<span v-if="favoritesCount" class="badge">{{ favoritesCount }}</span>
        </RouterLink>
        <RouterLink to="/about" class="nav-link">О проекте</RouterLink>
      </nav>
    </div>
  </header>

  <main class="container main">
    <RouterView v-slot="{ Component }">
      <component :is="Component" :meta="meta" />
    </RouterView>
  </main>

  <footer class="site-footer">
    <div class="container footer-text">
      <p>
        Цены и наличие обновляются раз в сутки<template v-if="meta">, последнее обновление — {{ formatDate(meta.generated_at) }}</template>.
        Перед покупкой проверяйте цену на сайте магазина.
      </p>
      <p class="muted">
        Data provided by <a href="https://www.discogs.com/" target="_blank" rel="noopener">Discogs</a>.
        This application uses Discogs’ API but is not affiliated with, sponsored or endorsed by Discogs.
        ‘Discogs’ is a trademark of Zink Media, LLC.
      </p>
    </div>
  </footer>
</template>
