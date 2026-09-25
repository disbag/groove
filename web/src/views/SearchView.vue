<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getSearchIndex } from '../api.js'
import { formatPrice, normalize } from '../format.js'

const route = useRoute()
const index = ref([])
const q = computed(() => String(route.query.q || ''))

getSearchIndex().then((rows) => {
  index.value = rows.map(([id, label, year, price]) => ({ id, label, year, price, key: normalize(label) }))
})

const results = computed(() => {
  const words = normalize(q.value).split(' ').filter(Boolean)
  if (!words.length) return []
  return index.value.filter((row) => words.every((w) => row.key.includes(w))).slice(0, 200)
})

watch(q, (value) => (document.title = `«${value}» · Groove`), { immediate: true })
</script>

<template>
  <section>
    <h1>Поиск: «{{ q }}»</h1>
    <p class="muted">Найдено: {{ results.length }}</p>
    <ul class="search-page">
      <li v-for="row in results" :key="row.id">
        <RouterLink :to="`/album/${row.id}`">{{ row.label }}</RouterLink>
        <span class="muted">{{ row.year || '' }}</span>
        <span class="price">от {{ formatPrice(row.price) }}</span>
      </li>
    </ul>
  </section>
</template>
