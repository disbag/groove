<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

defineProps({ genres: { type: Array, default: () => [] } })

const route = useRoute()
const open = ref(false)
const root = ref(null)

watch(() => route.fullPath, () => (open.value = false))

function onDocumentClick(event) {
  if (open.value && root.value && !root.value.contains(event.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))
</script>

<template>
  <div ref="root" class="genre-menu" @keydown.esc="open = false">
    <button
      type="button"
      class="nav-link nav-button"
      :class="{ 'router-link-active': route.name === 'genre' }"
      :aria-expanded="open"
      aria-controls="genre-menu-panel"
      @click="open = !open"
    >
      По жанрам <span aria-hidden="true" class="caret">▾</span>
    </button>
    <div v-show="open" id="genre-menu-panel" class="genre-panel">
      <nav class="container genre-panel-grid" aria-label="Жанры">
        <RouterLink to="/" class="genre-panel-link">Все жанры</RouterLink>
        <RouterLink v-for="g in genres" :key="g.slug" :to="`/genre/${g.slug}`" class="genre-panel-link">
          {{ g.ru }} <span class="muted">{{ g.count }}</span>
        </RouterLink>
      </nav>
    </div>
  </div>
</template>
