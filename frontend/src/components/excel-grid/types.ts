export interface ExcelFilterOption {
  value: string
  label: string
  count?: number
  checked?: boolean
  _checked?: boolean
}

export interface ExcelGridColumn {
  key: string
  label: string
  width?: number | string
  minWidth?: number | string
  align?: 'left' | 'center' | 'right'
  sortable?: boolean
  custom?: boolean
  dataType?: 'text' | 'number' | 'date' | 'boolean' | 'select'
  filters?: ExcelFilterOption[]
  filterMultiple?: boolean
  fixed?: 'left' | 'right'
  formatter?: (row: any) => string
}

export type ExcelGridFilterValues = Record<string, string[]>
