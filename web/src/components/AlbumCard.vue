<script setup>
import { RouterLink } from 'vue-router'
import CoverImage from './CoverImage.vue'
import { isFavorite, toggleFavorite } from '../favorites.js'
import { formatPrice, shopsLabel } from '../format.js'

defineProps({ album: { type: Object, required: true }, eager: Boolean })
</script>

<template>
  <article class="album-card">
    <RouterLink :to="`/album/${album.id}`" class="album-link">
      <div class="cover">
        <CoverImage
          :full="album.cv || album.c"
          :thumb="album.cv ? album.c : null"
          :fallback="album.s"
          :alt="`${album.a} — ${album.t}`"
          :eager="eager"
        />
        <span v-if="album.col" class="chip chip-colour" title="Есть цветные издания">цветной</span>
      </div>
      <div class="album-meta">
        <p class="album-artist">{{ album.a }}</p>
        <h3 class="album-title">{{ album.t }}</h3>
        <p class="album-price">
          <span class="price">от {{ formatPrice(album.p) }}</span>
          <span v-if="album.n" class="muted">{{ shopsLabel(album.n) }}</span>
        </p>
      </div>
    </RouterLink>
    <button
      class="fav-button"
      :class="{ active: isFavorite(album.id) }"
      :aria-pressed="isFavorite(album.id)"
      :aria-label="isFavorite(album.id) ? 'Убрать из избранного' : 'В избранное'"
      @click="toggleFavorite(album)"
    >
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path d="M12 21s-7.5-4.6-9.6-9.2C.9 8.4 3 4.5 6.8 4.5c2 0 3.6 1.1 4.4 2.6.8-1.5 2.4-2.6 4.4-2.6 3.8 0 5.9 3.9 4.4 7.3C19.5 16.4 12 21 12 21z" />
      </svg>
    </button>
  </article>
</template>
