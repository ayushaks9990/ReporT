import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from './AuthContext'
import { api } from '../lib/api'
import type { DatasetItem } from '../types'

type DatasetContextValue = {
  datasets: DatasetItem[]
  activeId: string
  activeDataset: DatasetItem | null
  setActiveId: (id: string) => void
  refreshDatasets: () => Promise<void>
  loadingDatasets: boolean
}

const DatasetContext = createContext<DatasetContextValue | null>(null)
const storageKey = 'ai-analytic-platform.activeDataset'

export function DatasetProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const [datasets, setDatasets] = useState<DatasetItem[]>([])
  const [activeId, setActiveIdState] = useState(() => localStorage.getItem(storageKey) || '')
  const [loadingDatasets, setLoadingDatasets] = useState(false)

  const setActiveId = useCallback((id: string) => {
    setActiveIdState(id)
    if (id) localStorage.setItem(storageKey, id)
    else localStorage.removeItem(storageKey)
  }, [])

  const refreshDatasets = useCallback(async () => {
    if (!user) {
      setDatasets([])
      setActiveId('')
      return
    }
    setLoadingDatasets(true)
    try {
      const result = await api<DatasetItem[]>('/datasets')
      setDatasets(result)
      if (activeId && !result.some((item) => item.id === activeId && item.status === 'ready')) {
        setActiveId('')
      }
    } finally {
      setLoadingDatasets(false)
    }
  }, [user, activeId, setActiveId])

  useEffect(() => {
    refreshDatasets().catch(() => undefined)
  }, [user])

  const activeDataset = datasets.find((item) => item.id === activeId) || null
  const value = useMemo(
    () => ({ datasets, activeId, activeDataset, setActiveId, refreshDatasets, loadingDatasets }),
    [datasets, activeId, activeDataset, setActiveId, refreshDatasets, loadingDatasets],
  )

  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>
}

export function useDatasets() {
  const value = useContext(DatasetContext)
  if (!value) throw new Error('useDatasets must be used inside DatasetProvider')
  return value
}
