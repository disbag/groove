<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlbumCard from '../components/AlbumCard.vue'
import { getCatalogPage } from '../api.js'
import { plural, SORTS } from '../format.js'

const props = defineProps({ meta: Object })
const route = useRoute()
const router = useRouter()

const genre = computed(() => route.query.g || 'all')
const sort = computed(() => (SORTS.some((s) => s.value === route.query.s) ? route.query.s : 'new'))

const items = ref([])
const page = ref(0)
const pages = ref(0)
const total = ref(0)
const loading = ref(false)
const error = ref('')

async function load(reset) {
  loading.value = true
  error.value = ''
  const next = reset ? 1 : page.value + 1
  try {
    const data = await getCatalogPage(genre.value, sort.value, next)
    items.value = reset ? data.items : [...items.value, ...data.items]
    page.value = data.page
    pages.value = data.pages
    total.value = data.total
  } catch {
    error.value = 'Не удалось загрузить каталог. Попробуйте обновить страницу.'
    if (reset) items.value = []
  } finally {
    loading.value = false
  }
}

watch([genre, sort], () => load(true), { immediate: true })

function setQuery(patch) {
  const query = { ...route.query, ...patch }
  if (query.g === 'all') delete query.g
  if (query.s === 'new') delete query.s
  router.replace({ query })
}

const genres = computed(() => props.meta?.genres || [])
</script>

<template>
  <section>
    <div class="catalog-head">
      <div>
        <h1>Новый винил в наличии</h1>
        <p v-if="meta" class="muted">
          {{ meta.albums }} {{ plural(meta.albums, 'альбом', 'альбома', 'альбомов') }} ·
          {{ meta.offers }} {{ plural(meta.offers, 'предложение', 'предложения', 'предложений') }} ·
          {{ meta.shops.length }} {{ plural(meta.shops.length, 'магазин', 'магазина', 'магазинов') }}
        </p>
      </div>
      <label class="sort">
        <span class="muted">Сортировка</span>
        <select :value="sort" @change="setQuery({ s: $event.target.value })">
          <option v-for="s in SORTS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </label>
    </div>

    <nav class="genres" aria-label="Жанры">
      <button class="genre-chip" :class="{ active: genre === 'all' }" @click="setQuery({ g: 'all' })">Все</button>
      <button
        v-for="g in genres"
        :key="g.slug"
        class="genre-chip"
        :class="{ active: genre === g.slug }"
        @click="setQuery({ g: g.slug })"
      >
        {{ g.ru }} <span class="muted">{{ g.count }}</span>
      </button>
    </nav>

    <p v-if="error" class="notice">{{ error }}</p>

    <div class="grid">
      <AlbumCard v-for="album in items" :key="album.id" :album="album" />
    </div>

    <div class="load-more">
      <p v-if="total" class="muted">Показано {{ items.length }} из {{ total }}</p>
      <button v-if="page < pages" class="button" :disabled="loading" @click="load(false)">
        {{ loading ? 'Загрузка…' : 'Показать ещё' }}
      </button>
    </div>
  </section>
</template>
