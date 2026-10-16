import { defineStore } from 'pinia'
import { ref } from 'vue'

export type CompanyKey = 'tianyue' | 'gaibo'

const storageKey = 'zephyr-company'

export const useCompanyStore = defineStore('company', () => {
  const savedCompany = typeof localStorage === 'undefined' ? null : localStorage.getItem(storageKey)
  const selectedCompany = ref<CompanyKey>(savedCompany === 'gaibo' ? 'gaibo' : 'tianyue')

  const setCompany = (company: CompanyKey) => {
    selectedCompany.value = company
    if (typeof localStorage !== 'undefined') localStorage.setItem(storageKey, company)
  }

  return { selectedCompany, setCompany }
})
