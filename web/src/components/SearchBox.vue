<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { formatPrice, normalize } from '../format.js'
import { findAlbums, loadSearchIndex } from '../search.js'

const SUGGESTIONS = 8

const route = useRoute()
const router = useRouter()
const query = ref('')
const open = ref(false)
// -1 — ничего не выбрано стрелками: Enter открывает страницу результатов
const active = ref(-1)
const index = ref(null)

// На странице поиска поле показывает текущий запрос
watch(
  () => route.name === 'search' && route.query.q,
  (q) => {
    if (q) query.value = String(q)
  },
  { immediate: true },
)

async function ensureIndex() {
  if (!index.value) index.value = await loadSearchIndex()
}

const matches = computed(() => (normalize(query.value).length < 2 ? [] : findAlbums(index.value, query.value)))
const suggestions = computed(() => matches.value.slice(0, SUGGESTIONS))
// Последний пункт подсказок — «Показать все»
const optionCount = computed(() => (suggestions.value.length ? suggestions.value.length + 1 : 0))

function onFocus() {
  open.value = true
  ensureIndex()
}

function onBlur() {
  setTimeout(() => (open.value = false), 150)
}

function onInput() {
  active.value = -1
  open.value = true
}

function goAlbum(row) {
  open.value = false
  query.value = ''
  router.push(`/album/${row.id}`)
}

function showAll() {
  const q = query.value.trim()
  if (!q) return
  open.value = false
  active.value = -1
  router.push({ name: 'search', query: { q } })
}

function submit() {
  const row = suggestions.value[active.value]
  if (row) goAlbum(row)
  else showAll()
}

function move(step) {
  const n = optionCount.value
  if (!n) return
  open.value = true
  active.value = active.value < 0 && step < 0 ? n - 1 : (active.value + step + n) % n
}
</script>

<template>
  <form class="search" role="search" @submit.prevent="submit">
    <input
      v-model="query"
      type="search"
      placeholder="Исполнитель или альбом"
      aria-label="Поиск по каталогу"
      autocomplete="off"
      enterkeyhint="search"
      @focus="onFocus"
      @blur="onBlur"
      @input="onInput"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.esc="open = false"
    />
    <ul v-if="open && suggestions.length" class="search-results" role="listbox">
      <li
        v-for="(row, i) in suggestions"
        :key="row.id"
        :class="{ active: i === active }"
        role="option"
        :aria-selected="i === active"
        @mousedown.prevent="goAlbum(row)"
      >
        <span class="search-label">{{ row.label }}</span>
        <span class="muted">{{ row.year || '' }} · от {{ formatPrice(row.price) }}</span>
      </li>
      <li
        class="search-all"
        :class="{ active: active === suggestions.length }"
        role="option"
        :aria-selected="active === suggestions.length"
        @mousedown.prevent="showAll"
      >
        Показать все<span class="muted"> · {{ matches.length }}</span>
      </li>
    </ul>
  </form>
</template>
