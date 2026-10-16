<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getArtists } from '../api.js'
import { normalize, plural } from '../format.js'

document.title = 'Исполнители · Groove'

const artists = ref(null)
const error = ref(false)
const filter = ref('')

getArtists()
  .then((rows) =>
    (artists.value = rows.map(([slug, name, count, price, letter]) => ({ slug, name, count, price, letter, key: normalize(name) }))),
  )
  .catch(() => (error.value = true))

const filtered = computed(() => {
  const words = normalize(filter.value).split(' ').filter(Boolean)
  const list = artists.value || []
  return words.length ? list.filter((a) => words.every((w) => a.key.includes(w))) : list
})

// Список уже отсортирован при выгрузке; группируем по букве указателя
const groups = computed(() => {
  const result = []
  for (const artist of filtered.value) {
    const last = result[result.length - 1]
    if (last && last.letter === artist.letter) last.items.push(artist)
    else result.push({ letter: artist.letter, items: [artist] })
  }
  return result
})

const anchor = (letter) => `letter-${letter === '#' ? 'num' : letter}`

function jump(letter) {
  document.getElementById(anchor(letter))?.scrollIntoView({ behavior: 'smooth' })
}
</script>

<template>
  <section>
    <h1>Исполнители</h1>
    <p v-if="error" class="notice">Не удалось загрузить список. Попробуйте обновить страницу.</p>
    <p v-else-if="!artists" class="muted">Загрузка…</p>
    <template v-else>
      <p class="muted">{{ artists.length }} {{ plural(artists.length, 'исполнитель', 'исполнителя', 'исполнителей') }} с пластинками в наличии</p>
      <div class="artists-tools">
        <input v-model="filter" class="artists-filter" type="search" placeholder="Найти исполнителя" aria-label="Найти исполнителя" />
        <nav class="letters" aria-label="Алфавитный указатель">
          <a v-for="g in groups" :key="g.letter" :href="`#${anchor(g.letter)}`" @click.prevent="jump(g.letter)">{{ g.letter }}</a>
        </nav>
      </div>
      <p v-if="!filtered.length" class="muted">Никого не нашлось.</p>
      <section v-for="g in groups" :id="anchor(g.letter)" :key="g.letter" class="letter-group">
        <h2>{{ g.letter }}</h2>
        <ul class="artist-list">
          <li v-for="a in g.items" :key="a.slug">
            <RouterLink :to="`/artist/${a.slug}`">{{ a.name }}</RouterLink>
            <span class="muted artist-count">{{ a.count }}</span>
          </li>
        </ul>
      </section>
    </template>
  </section>
</template>
