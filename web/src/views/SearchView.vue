<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { formatPrice, plural } from '../format.js'
import { findAlbums, loadSearchIndex } from '../search.js'

const PAGE = 100

const route = useRoute()
const index = ref(null)
const error = ref(false)
const shown = ref(PAGE)
const q = computed(() => String(route.query.q || '').trim())

loadSearchIndex()
  .then((rows) => (index.value = rows))
  .catch(() => (error.value = true))

const results = computed(() => findAlbums(index.value, q.value))

watch(
  q,
  (value) => {
    shown.value = PAGE
    document.title = `«${value}» · Groove`
  },
  { immediate: true },
)
</script>

<template>
  <section>
    <h1>Поиск: «{{ q }}»</h1>
    <p v-if="error" class="notice">Не удалось загрузить поиск. Попробуйте обновить страницу.</p>
    <p v-else-if="!index" class="muted">Загрузка…</p>
    <p v-else-if="!results.length" class="muted">Ничего не нашлось. Попробуйте написать иначе или только исполнителя.</p>
    <p v-else class="muted">
      {{ results.length }} {{ plural(results.length, 'альбом', 'альбома', 'альбомов') }}
    </p>
    <ul class="search-page">
      <li v-for="row in results.slice(0, shown)" :key="row.id">
        <RouterLink :to="`/album/${row.id}`">{{ row.label }}</RouterLink>
        <span class="muted">{{ row.year || '' }}</span>
        <span class="price">от {{ formatPrice(row.price) }}</span>
      </li>
    </ul>
    <div v-if="results.length > shown" class="load-more">
      <p class="muted">Показано {{ shown }} из {{ results.length }}</p>
      <button class="button" @click="shown += PAGE">Показать ещё</button>
    </div>
  </section>
</template>
