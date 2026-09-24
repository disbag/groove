import { createRouter, createWebHashHistory } from 'vue-router'
import CatalogView from './views/CatalogView.vue'

// Хеш-роутинг: GitHub Pages не умеет отдавать index.html на произвольные пути.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'catalog', component: CatalogView },
    { path: '/album/:id', name: 'album', component: () => import('./views/AlbumView.vue'), props: true },
    { path: '/search', name: 'search', component: () => import('./views/SearchView.vue') },
    { path: '/favorites', name: 'favorites', component: () => import('./views/FavoritesView.vue') },
    { path: '/about', name: 'about', component: () => import('./views/AboutView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(to, from, saved) {
    return saved || { top: 0 }
  },
})

// Страницы альбома и поиска ставят свой заголовок сами
router.afterEach((to) => {
  if (!['album', 'search'].includes(to.name)) document.title = 'Винил · цены'
})
