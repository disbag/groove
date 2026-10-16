<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import CoverImage from '../components/CoverImage.vue'
import { getAlbum } from '../api.js'
import { isFavorite, toggleFavorite } from '../favorites.js'
import { COLOR_LABELS, formatPrice, plural, shopsLabel } from '../format.js'

const props = defineProps({ id: String, meta: Object })
const router = useRouter()
// Пришли со страницы сайта (каталог, жанр, исполнитель, поиск) — «назад» возвращает туда же, на то же место
const cameFromSite = Boolean(window.history.state?.back)
const album = ref(null)
const missing = ref(false)

watch(
  () => props.id,
  async (id) => {
    album.value = null
    missing.value = false
    try {
      const data = await getAlbum(id)
      if (id !== props.id) return // пока грузилось, перешли на другой альбом
      album.value = data
      document.title = `${data.artist} — ${data.title} · Groove`
    } catch {
      if (id === props.id) missing.value = true
    }
  },
  { immediate: true },
)

const genreNames = computed(() => {
  const map = Object.fromEntries((props.meta?.genres || []).map((g) => [g.name, g.ru]))
  return (album.value?.genres || []).map((g) => map[g] || g)
})
const shopCount = computed(() => new Set((album.value?.offers || []).map((o) => o.shop)).size)
const snapshot = computed(() =>
  album.value && {
    id: album.value.id, a: album.value.artist, t: album.value.title, c: album.value.thumb || album.value.cover,
    cv: album.value.cover,
    s: album.value.shop_image, p: album.value.min_price,
  },
)

function edition(offer) {
  return [offer.year, offer.country, offer.label].filter(Boolean).join(' · ')
}
</script>

<template>
  <section v-if="missing" class="empty">
    <h1>Альбом не найден</h1>
    <p class="muted">Возможно, он закончился во всех магазинах.</p>
    <RouterLink to="/" class="button">В каталог</RouterLink>
  </section>

  <section v-else-if="album" class="album-page">
    <a v-if="cameFromSite" href="#" class="back muted" @click.prevent="router.back()">← Назад</a>
    <RouterLink v-else to="/" class="back muted">← Каталог</RouterLink>
    <div class="album-layout">
      <div class="album-cover">
        <CoverImage
          :full="album.cover"
          :thumb="album.thumb"
          :fallback="album.shop_image"
          :alt="`${album.artist} — ${album.title}`"
          eager
        />
      </div>

      <div class="album-info">
        <p class="album-artist big">
          <RouterLink v-if="album.artist_slug" :to="`/artist/${album.artist_slug}`" class="artist-link">{{ album.artist }}</RouterLink>
          <template v-else>{{ album.artist }}</template>
        </p>
        <h1 class="album-name">{{ album.title }}</h1>
        <p class="muted">
          <span v-if="album.year">{{ album.year }}</span>
          <span v-if="genreNames.length"> · {{ genreNames.join(', ') }}</span>
        </p>
        <p v-if="album.styles?.length" class="styles">
          <span v-for="s in album.styles" :key="s" class="chip">{{ s }}</span>
        </p>

        <div class="price-row">
          <div>
            <p class="price big">от {{ formatPrice(album.min_price) }}</p>
            <p class="muted">в наличии в {{ shopCount }} {{ plural(shopCount, 'магазине', 'магазинах', 'магазинах') }}</p>
          </div>
          <button class="button" :class="{ secondary: isFavorite(album.id) }" @click="toggleFavorite(snapshot)">
            {{ isFavorite(album.id) ? '♥ В избранном' : '♡ В избранное' }}
          </button>
        </div>

        <h2 class="section-title">Где купить</h2>
        <ul class="offers">
          <li v-for="(offer, i) in album.offers" :key="i" class="offer">
            <div class="offer-shop">
              <strong>{{ offer.shop_name }}</strong>
              <span v-if="edition(offer)" class="muted">{{ edition(offer) }}</span>
            </div>
            <div class="offer-tags">
              <span class="chip" :class="`chip-${offer.color}`" :title="offer.color_raw || ''">
                {{ COLOR_LABELS[offer.color] || offer.color }}
              </span>
              <span v-if="offer.lp" class="chip">{{ offer.lp }} LP</span>
            </div>
            <div class="offer-buy">
              <span class="price" :class="{ best: offer.price === album.min_price }">{{ formatPrice(offer.price) }}</span>
              <a class="button small" :href="offer.url" target="_blank" rel="noopener">В магазин</a>
            </div>
          </li>
        </ul>

        <template v-if="album.tracklist?.length">
          <h2 class="section-title">Треклист <span class="muted">· {{ album.tracklist.length }}</span></h2>
          <ol class="tracklist">
            <li v-for="(t, i) in album.tracklist" :key="i">
              <span class="muted">{{ t.p }}</span> {{ t.t }} <span class="muted">{{ t.d }}</span>
            </li>
          </ol>
        </template>

        <p v-if="album.discogs" class="attribution muted">
          Data provided by <a :href="album.discogs" target="_blank" rel="noopener">Discogs</a> — полная информация об альбоме и всех изданиях.
        </p>
      </div>
    </div>
  </section>

  <p v-else class="muted">Загрузка…</p>
</template>
