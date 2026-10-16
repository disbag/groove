import { createRouter, createWebHashHistory } from 'vue-router'
import CatalogView from './views/CatalogView.vue'

// Хеш-роутинг: GitHub Pages не умеет отдавать index.html на произвольные пути.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'catalog',
      component: CatalogView,
      // старые ссылки вида /?g=rock ведут на страницу жанра
      beforeEnter: (to) => {
        if (!to.query.g) return true
        const { g, ...query } = to.query
        return g === 'all' ? { path: '/', query } : { name: 'genre', params: { genre: g }, query }
      },
    },
    { path: '/genre/:genre', name: 'genre', component: CatalogView },
    { path: '/artists', name: 'artists', component: () => import('./views/ArtistsView.vue') },
    { path: '/artist/:slug', name: 'artist', component: () => import('./views/ArtistView.vue'), props: true },
    { path: '/album/:id', name: 'album', component: () => import('./views/AlbumView.vue'), props: true },
    { path: '/search', name: 'search', component: () => import('./views/SearchView.vue') },
    { path: '/favorites', name: 'favorites', component: () => import('./views/FavoritesView.vue') },
    { path: '/about', name: 'about', component: () => import('./views/AboutView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(to, from, saved) {
    if (!saved) return { top: 0 }
    // Назад к списку: ждём, пока страница снова отрисует столько же, сколько было, и только потом прокручиваем
    return new Promise((resolve) => {
      const started = Date.now()
      const tryScroll = () => {
        const tallEnough = document.documentElement.scrollHeight >= saved.top + window.innerHeight
        if (tallEnough || Date.now() - started > 1500) resolve(saved)
        else requestAnimationFrame(tryScroll)
      }
      tryScroll()
    })
  },
})

// Страницы альбома, поиска, жанра и исполнителя ставят свой заголовок сами
router.afterEach((to) => {
  if (!['album', 'search', 'genre', 'artist', 'artists'].includes(to.name)) document.title = 'Groove — цены на винил'
})
