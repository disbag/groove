<script setup>
import { ref, watchEffect } from 'vue'
import { RouterLink } from 'vue-router'
import AlbumCard from '../components/AlbumCard.vue'
import { getAlbum } from '../api.js'
import { favorites } from '../favorites.js'

// Сохранённый снимок + свежие данные карточки: цена могла измениться, альбом — закончиться.
const fresh = ref({})

watchEffect(() => {
  for (const item of favorites.value) {
    if (fresh.value[item.id] !== undefined) continue
    fresh.value[item.id] = null
    getAlbum(item.id)
      .then((album) => (fresh.value[item.id] = album))
      .catch(() => (fresh.value[item.id] = false))
  }
})

function view(item) {
  const album = fresh.value[item.id]
  if (!album) return item
  return { ...item, p: album.min_price, n: new Set(album.offers.map((o) => o.shop)).size }
}
</script>

<template>
  <section>
    <h1>Избранное</h1>
    <p class="muted">Список хранится только в этом браузере — регистрация не нужна.</p>
    <div v-if="!favorites.length" class="empty">
      <p>Пока пусто. Нажмите ♡ на обложке альбома, чтобы сохранить его здесь.</p>
      <RouterLink to="/" class="button">В каталог</RouterLink>
    </div>
    <div v-else class="grid">
      <div v-for="item in favorites" :key="item.id" class="fav-item">
        <AlbumCard :album="view(item)" />
        <p v-if="fresh[item.id] === false" class="notice small">Сейчас нет в наличии</p>
      </div>
    </div>
  </section>
</template>
