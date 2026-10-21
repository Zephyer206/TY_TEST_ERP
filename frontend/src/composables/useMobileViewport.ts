import { onMounted, onUnmounted, ref } from 'vue'

export function useMobileViewport() {
  const query = window.matchMedia('(max-width: 767px)')
  const isMobile = ref(query.matches)
  const update = () => { isMobile.value = query.matches }
  onMounted(() => query.addEventListener('change', update))
  onUnmounted(() => query.removeEventListener('change', update))
  return isMobile
}
