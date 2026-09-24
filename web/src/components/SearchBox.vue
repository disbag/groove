<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSearchIndex } from '../api.js'
import { formatPrice, normalize } from '../format.js'

const router = useRouter()
const query = ref('')
const open = ref(false)
const active = ref(0)
const index = ref(null)

async function ensureIndex() {
  if (index.value) return
  const rows = await getSearchIndex()
  index.value = rows.map(([id, label, year, price]) => ({ id, label, year, price, key: normalize(label) }))
}

const results = computed(() => {
  const q = normalize(query.value)
  if (!index.value || q.length < 2) return []
  const words = q.split(' ')
  return index.value.filter((row) => words.every((w) => row.key.includes(w))).slice(0, 8)
})

function onFocus() {
  open.value = true
  ensureIndex()
}

function onBlur() {
  setTimeout(() => (open.value = false), 150)
}

function go(row) {
  open.value = false
  query.value = ''
  router.push(`/album/${row.id}`)
}

function submit() {
  if (results.value[active.value]) return go(results.value[active.value])
  if (query.value.trim()) {
    router.push({ name: 'search', query: { q: query.value.trim() } })
    open.value = false
  }
}

function move(step) {
  const n = results.value.length
  if (n) active.value = (active.value + step + n) % n
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
      @focus="onFocus"
      @blur="onBlur"
      @input="active = 0"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.esc="open = false"
    />
    <ul v-if="open && results.length" class="search-results" role="listbox">
      <li
        v-for="(row, i) in results"
        :key="row.id"
        :class="{ active: i === active }"
        role="option"
        @mousedown.prevent="go(row)"
      >
        <span class="search-label">{{ row.label }}</span>
        <span class="muted">{{ row.year || '' }} · от {{ formatPrice(row.price) }}</span>
      </li>
    </ul>
  </form>
</template>
