<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AlbumCard from '../components/AlbumCard.vue'
import { EAGER_CARDS } from '../format.js'
import { getCatalogPage } from '../api.js'
import { plural, SORTS } from '../format.js'
import { loadedPages } from '../catalogState.js'

const props = defineProps({ meta: Object })
const route = useRoute()
const router = useRouter()

const genre = computed(() => route.params.genre || 'all')
const sort = computed(() => (SORTS.some((s) => s.value === route.query.s) ? route.query.s : 'new'))
const genreInfo = computed(() => (props.meta?.genres || []).find((g) => g.slug === genre.value))
const sortQuery = computed(() => (sort.value === 'new' ? {} : { s: sort.value }))

const items = ref([])
const page = ref(0)
const pages = ref(0)
const total = ref(0)
const loading = ref(false)
const error = ref('')

// Номер последнего запроса: ответ на устаревший (жанр уже переключили) отбрасываем
let lastRequest = 0

async function load(reset) {
  const key = `${genre.value}|${sort.value}`
  // Вернулись к списку (например, со страницы альбома) — показываем столько же страниц, сколько было
  const saved = reset && loadedPages.get(key)
  if (saved) {
    lastRequest++
    items.value = saved.items
    page.value = saved.page
    pages.value = saved.pages
    total.value = saved.total
    loading.value = false
    error.value = ''
    return
  }
  const request = ++lastRequest
  loading.value = true
  error.value = ''
  const next = reset ? 1 : page.value + 1
  try {
    const data = await getCatalogPage(genre.value, sort.value, next)
    if (request !== lastRequest) return
    items.value = reset ? data.items : [...items.value, ...data.items]
    page.value = data.page
    pages.value = data.pages
    total.value = data.total
    loadedPages.set(key, { items: items.value, page: page.value, pages: pages.value, total: total.value })
  } catch {
    if (request !== lastRequest) return
    error.value = 'Не удалось загрузить каталог. Попробуйте обновить страницу.'
    if (reset) items.value = []
  } finally {
    if (request === lastRequest) loading.value = false
  }
}

watch([genre, sort], () => load(true), { immediate: true })

watch(
  genreInfo,
  (g) => {
    if (route.name === 'genre') document.title = g ? `${g.ru} — новый винил · Groove` : 'Groove — цены на винил'
  },
  { immediate: true },
)

function setSort(value) {
  const query = { ...route.query, s: value }
  if (value === 'new') delete query.s
  router.replace({ query })
}

const genres = computed(() => props.meta?.genres || [])
</script>

<template>
  <section>
    <div class="catalog-head">
      <div>
        <h1>{{ genreInfo ? `${genreInfo.ru}: новый винил в наличии` : 'Новый винил в наличии' }}</h1>
        <p v-if="meta && genre === 'all'" class="muted">
          {{ meta.albums }} {{ plural(meta.albums, 'альбом', 'альбома', 'альбомов') }} ·
          {{ meta.offers }} {{ plural(meta.offers, 'предложение', 'предложения', 'предложений') }} ·
          {{ meta.shops.length }} {{ plural(meta.shops.length, 'магазин', 'магазина', 'магазинов') }}
        </p>
        <p v-else-if="total" class="muted">{{ total }} {{ plural(total, 'альбом', 'альбома', 'альбомов') }}</p>
      </div>
      <label class="sort">
        <span class="muted">Сортировка</span>
        <select :value="sort" @change="setSort($event.target.value)">
          <option v-for="s in SORTS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </label>
    </div>

    <nav class="genres" aria-label="Жанры">
      <RouterLink class="genre-chip" :class="{ active: genre === 'all' }" :to="{ path: '/', query: sortQuery }">
        Все
      </RouterLink>
      <RouterLink
        v-for="g in genres"
        :key="g.slug"
        class="genre-chip"
        :class="{ active: genre === g.slug }"
        :to="{ path: `/genre/${g.slug}`, query: sortQuery }"
      >
        {{ g.ru }} <span class="muted">{{ g.count }}</span>
      </RouterLink>
    </nav>

    <p v-if="error" class="notice">{{ error }}</p>

    <div class="grid">
      <AlbumCard v-for="(album, i) in items" :key="album.id" :album="album" :eager="i < EAGER_CARDS" />
    </div>

    <div class="load-more">
      <p v-if="total" class="muted">Показано {{ items.length }} из {{ total }}</p>
      <button v-if="page < pages" class="button" :disabled="loading" @click="load(false)">
        {{ loading ? 'Загрузка…' : 'Показать ещё' }}
      </button>
    </div>
  </section>
</template>
