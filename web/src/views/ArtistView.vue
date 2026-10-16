<script setup>
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import AlbumCard from '../components/AlbumCard.vue'
import { EAGER_CARDS } from '../format.js'
import { getArtist } from '../api.js'
import { plural } from '../format.js'

const props = defineProps({ slug: String })
const artist = ref(null)
const missing = ref(false)

watch(
  () => props.slug,
  async (slug) => {
    artist.value = null
    missing.value = false
    try {
      const data = await getArtist(slug)
      if (slug !== props.slug) return
      artist.value = data
      document.title = `${data.name} — винил · Groove`
    } catch {
      if (slug === props.slug) missing.value = true
    }
  },
  { immediate: true },
)
</script>

<template>
  <section v-if="missing" class="empty">
    <h1>Исполнитель не найден</h1>
    <p class="muted">Возможно, его пластинки закончились во всех магазинах.</p>
    <RouterLink to="/artists" class="button">Все исполнители</RouterLink>
  </section>
  <section v-else-if="artist">
    <RouterLink to="/artists" class="back muted">← Все исполнители</RouterLink>
    <h1>{{ artist.name }}</h1>
    <p class="muted">{{ artist.albums.length }} {{ plural(artist.albums.length, 'альбом', 'альбома', 'альбомов') }} в наличии</p>
    <div class="grid">
      <AlbumCard v-for="(album, i) in artist.albums" :key="album.id" :album="album" :eager="i < EAGER_CARDS" />
    </div>
  </section>
  <p v-else class="muted">Загрузка…</p>
</template>
