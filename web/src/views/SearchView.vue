<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AlbumCard from '../components/AlbumCard.vue'
import { getAlbum } from '../api.js'
import { plural } from '../format.js'
import { findAlbums, loadSearchIndex } from '../search.js'

const PAGE = 48

const route = useRoute()
const index = ref(null)
const error = ref(false)
const shown = ref(PAGE)
// Данные карточек для обложек: id → элемент как в каталоге. В индексе поиска обложек нет —
// догружаем карточки альбомов только для показанных результатов.
const details = reactive({})
const q = computed(() => String(route.query.q || '').trim())

loadSearchIndex()
  .then((rows) => (index.value = rows))
  .catch(() => (error.value = true))

const results = computed(() => findAlbums(index.value, q.value))
const visible = computed(() => results.value.slice(0, shown.value).map((row) => details[row.id] || fromIndex(row)))

// Пока карточка не загрузилась — то, что есть в индексе: исполнитель, альбом, цена
function fromIndex(row) {
  const [a, ...t] = row.label.split(' — ')
  return { id: row.id, a, t: t.join(' — '), p: row.price, y: row.year }
}

function toItem(album) {
  return {
    id: album.id, a: album.artist, t: album.title, y: album.year, p: album.min_price,
    c: album.thumb || album.cover, cv: album.cover, s: album.shop_image,
    n: new Set(album.offers.map((o) => o.shop)).size,
    col: album.offers.some((o) => o.color !== 'black'),
  }
}

watch(
  visible,
  (items) => {
    for (const item of items) {
      if (item.id in details) continue
      details[item.id] = null // загружается
      getAlbum(item.id)
        .then((album) => (details[item.id] = toItem(album)))
        .catch(() => delete details[item.id])
    }
  },
  { immediate: true },
)

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
    <div class="grid">
      <AlbumCard v-for="album in visible" :key="album.id" :album="album" />
    </div>
    <div v-if="results.length" class="load-more">
      <p class="muted">Показано {{ visible.length }} из {{ results.length }}</p>
      <button v-if="results.length > shown" class="button" @click="shown += PAGE">Показать ещё</button>
    </div>
  </section>
</template>
