<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { isFavorite, toggleFavorite } from '../favorites.js'
import { formatPrice, shopsLabel } from '../format.js'

const props = defineProps({ album: { type: Object, required: true } })

// Если обложка Discogs не загрузилась (Cloudflare в РФ), показываем фото из магазина
const failed = ref(false)
const src = computed(() => (failed.value ? props.album.s : props.album.cv || props.album.c))
const srcset = computed(() =>
  !failed.value && props.album.c && props.album.cv ? `${props.album.c} 150w, ${props.album.cv} 600w` : undefined,
)
function onError() {
  if (!failed.value && props.album.s) failed.value = true
}
</script>

<template>
  <article class="album-card">
    <RouterLink :to="`/album/${album.id}`" class="album-link">
      <div class="cover">
        <img
          v-if="src"
          :src="src"
          :srcset="srcset"
          sizes="(max-width: 600px) 45vw, 220px"
          :alt="`${album.a} — ${album.t}`"
          loading="lazy"
          referrerpolicy="no-referrer"
          @error="onError"
        />
        <div v-else class="cover-placeholder" aria-hidden="true"></div>
        <span v-if="album.col" class="chip chip-colour" title="Есть цветные издания">цветной</span>
      </div>
      <div class="album-meta">
        <p class="album-artist">{{ album.a }}</p>
        <h3 class="album-title">{{ album.t }}</h3>
        <p class="album-price">
          <span class="price">от {{ formatPrice(album.p) }}</span>
          <span class="muted">{{ shopsLabel(album.n) }}</span>
        </p>
      </div>
    </RouterLink>
    <button
      class="fav-button"
      :class="{ active: isFavorite(album.id) }"
      :aria-pressed="isFavorite(album.id)"
      :aria-label="isFavorite(album.id) ? 'Убрать из избранного' : 'В избранное'"
      @click="toggleFavorite(props.album)"
    >
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path d="M12 21s-7.5-4.6-9.6-9.2C.9 8.4 3 4.5 6.8 4.5c2 0 3.6 1.1 4.4 2.6.8-1.5 2.4-2.6 4.4-2.6 3.8 0 5.9 3.9 4.4 7.3C19.5 16.4 12 21 12 21z" />
      </svg>
    </button>
  </article>
</template>
