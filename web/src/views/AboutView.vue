<script setup>
import { formatDate, plural } from '../format.js'

defineProps({ meta: Object })
</script>

<template>
  <section class="prose">
    <h1>О проекте</h1>
    <p>
      <strong>Groove</strong> — некоммерческий проект: актуальные цены на <strong>новые</strong> виниловые пластинки
      в российских магазинах в одном месте.
      Каждую ночь робот обходит каталоги магазинов, сопоставляет позиции с базой Discogs по штрихкоду
      и показывает, где альбом сейчас есть в наличии и сколько стоит.
    </p>
    <p>Регистрации нет: избранное хранится только в вашем браузере.</p>

    <h2>Магазины</h2>
    <ul v-if="meta">
      <li v-for="shop in meta.shops" :key="shop.code">
        <a :href="shop.url" target="_blank" rel="noopener">{{ shop.name }}</a>
        <span class="muted"> — {{ shop.offers }} {{ plural(shop.offers, 'позиция', 'позиции', 'позиций') }}</span>
      </li>
    </ul>
    <p v-if="meta" class="muted">Последнее обновление: {{ formatDate(meta.generated_at) }}.</p>

    <h2>Данные</h2>
    <p>
      Названия, годы, жанры, треклисты и обложки — из
      <a href="https://www.discogs.com/" target="_blank" rel="noopener">Discogs</a>. Data provided by Discogs.
    </p>
    <p class="muted">
      This application uses Discogs’ API but is not affiliated with, sponsored or endorsed by Discogs.
      ‘Discogs’ is a trademark of Zink Media, LLC.
    </p>
    <p class="muted">
      Цены и наличие берутся с публичных страниц магазинов и могут отличаться от актуальных — перед покупкой
      проверяйте на сайте магазина.
    </p>
  </section>
</template>
