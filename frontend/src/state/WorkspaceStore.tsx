import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { Paper, WorkspaceBrief, WorkspaceDetail, WorkspaceSummary } from '../api/types'
import { paperKey } from '../api/types'

type ToastTone = 'info' | 'error' | 'success'
type Toast = { id: number; message: string; tone: ToastTone }

type Selection = {
  workspaceId: number | null
  papers: Paper[]
}

type BriefPayload = {
  mode: 'summary' | 'compare' | 'question' | 'extract' | 'reading_path' | 'export'
  style: string
  title: string
  body: string
  source_papers: Paper[]
}

type StoreValue = {
  workspaces: WorkspaceSummary[]
  workspaceDetails: Record<number, WorkspaceDetail>
  loadingWorkspaces: boolean
  selection: Selection
  toasts: Toast[]
  refreshWorkspaces: () => Promise<WorkspaceSummary[]>
  refreshWorkspace: (id: number) => Promise<WorkspaceDetail | null>
  createWorkspace: (title?: string) => Promise<WorkspaceDetail | null>
  updateWorkspace: (id: number, payload: { title?: string; notes?: string }) => Promise<WorkspaceSummary | null>
  deleteWorkspace: (id: number) => Promise<void>
  savePaper: (workspaceId: number, paper: Paper) => Promise<void>
  removePaper: (workspaceId: number, paper: Paper) => Promise<void>
  togglePaperSelection: (workspaceId: number, paper: Paper) => void
  clearSelection: () => void
  setSelection: (workspaceId: number, papers: Paper[]) => void
  isSelected: (paper: Paper) => boolean
  pushToast: (message: string, tone?: ToastTone) => void
  dismissToast: (id: number) => void
  recordBrief: (workspaceId: number, brief: BriefPayload) => Promise<void>
  deleteBrief: (workspaceId: number, briefId: number) => Promise<void>
  updateWorkspaceState: (workspaceId: number, key: string, value: Record<string, unknown>) => Promise<void>
  updatePaperNote: (workspaceId: number, paper: Paper, note: string) => Promise<void>
}

const StoreContext = createContext<StoreValue | null>(null)

function persistSelection(workspaceId: number, papers: Paper[]) {
  void api.updateWorkspaceState(workspaceId, 'selection', {
    papers: papers.map((paper) => ({ source: paper.source, external_id: paper.external_id })),
  })
}

export function WorkspaceStoreProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [workspaceDetails, setWorkspaceDetails] = useState<Record<number, WorkspaceDetail>>({})
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(true)
  const [selection, setSelectionState] = useState<Selection>({ workspaceId: null, papers: [] })
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastIdRef = useRef(0)

  const pushToast = useCallback((message: string, tone: ToastTone = 'info') => {
    toastIdRef.current += 1
    const id = toastIdRef.current
    setToasts((current) => [...current, { id, message, tone }])
    setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, 4500)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const refreshWorkspaces = useCallback(async () => {
    try {
      const data = await api.listWorkspaces()
      setWorkspaces(data)
      return data
    } catch (caught) {
      pushToast(caught instanceof Error ? caught.message : 'Failed to load workspaces.', 'error')
      return []
    } finally {
      setLoadingWorkspaces(false)
    }
  }, [pushToast])

  const refreshWorkspace = useCallback(
    async (id: number) => {
      try {
        const detail = await api.getWorkspace(id)
        setWorkspaceDetails((current) => ({ ...current, [id]: detail }))
        setSelectionState((current) => {
          if (current.workspaceId !== null && current.workspaceId !== id) return current
          const savedSelection = detail.state.find((entry) => entry.state_key === 'selection')
          const rawPapers = savedSelection?.value?.papers
          if (!Array.isArray(rawPapers)) return current
          const keys = new Set(
            rawPapers
              .map((item) =>
                item &&
                typeof item === 'object' &&
                'source' in item &&
                'external_id' in item
                  ? `${String(item.source)}::${String(item.external_id)}`
                  : '',
              )
              .filter(Boolean),
          )
          if (keys.size === 0) return current
          return { workspaceId: id, papers: detail.saved_papers.filter((paper) => keys.has(paperKey(paper))) }
        })
        setWorkspaces((current) => {
          const stub: WorkspaceSummary = {
            id: detail.id,
            title: detail.title,
            notes: detail.notes,
            saved_paper_count: detail.saved_paper_count,
            search_count: detail.search_count,
            created_at: detail.created_at,
            updated_at: detail.updated_at,
          }
          if (current.some((w) => w.id === id)) {
            return current.map((w) => (w.id === id ? stub : w))
          }
          return [stub, ...current]
        })
        return detail
      } catch (caught) {
        pushToast(caught instanceof Error ? caught.message : 'Failed to load workspace.', 'error')
        return null
      }
    },
    [pushToast],
  )

  const createWorkspace = useCallback(
    async (title = 'New workspace') => {
      try {
        const created = await api.createWorkspace(title)
        setWorkspaceDetails((current) => ({ ...current, [created.id]: created }))
        await refreshWorkspaces()
        pushToast('Workspace created', 'success')
        return created
      } catch (caught) {
        pushToast(caught instanceof Error ? caught.message : 'Failed to create workspace.', 'error')
        return null
      }
    },
    [pushToast, refreshWorkspaces],
  )

  const updateWorkspace = useCallback(
    async (id: number, payload: { title?: string; notes?: string }) => {
      try {
        const summary = await api.updateWorkspace(id, payload)
        setWorkspaceDetails((current) => {
          const existing = current[id]
          if (!existing) return current
          return {
            ...current,
            [id]: {
              ...existing,
              title: summary.title,
              notes: summary.notes,
              updated_at: summary.updated_at,
              saved_paper_count: summary.saved_paper_count,
              search_count: summary.search_count,
            },
          }
        })
        setWorkspaces((current) => current.map((w) => (w.id === id ? summary : w)))
        return summary
      } catch (caught) {
        pushToast(caught instanceof Error ? caught.message : 'Failed to update workspace.', 'error')
        return null
      }
    },
    [pushToast],
  )

  const deleteWorkspace = useCallback(
    async (id: number) => {
      try {
        await api.deleteWorkspace(id)
        setWorkspaceDetails((current) => {
          const next = { ...current }
          delete next[id]
          return next
        })
        setWorkspaces((current) => current.filter((w) => w.id !== id))
        setSelectionState((current) => (current.workspaceId === id ? { workspaceId: null, papers: [] } : current))
        pushToast('Workspace deleted', 'success')
      } catch (caught) {
        pushToast(caught instanceof Error ? caught.message : 'Failed to delete workspace.', 'error')
      }
    },
    [pushToast],
  )

  const savePaper = useCallback(
    async (workspaceId: number, paper: Paper) => {
      try {
        await api.savePaper(workspaceId, paper)
        await refreshWorkspace(workspaceId)
        pushToast('Saved to workspace', 'success')
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : 'Failed to save paper.'
        pushToast(message, 'error')
      }
    },
    [pushToast, refreshWorkspace],
  )

  const removePaper = useCallback(
    async (workspaceId: number, paper: Paper) => {
      try {
        await api.removePaper(workspaceId, paper.source, paper.external_id)
        await refreshWorkspace(workspaceId)
        setSelectionState((current) => ({
          workspaceId: current.workspaceId,
          papers: current.papers.filter((p) => paperKey(p) !== paperKey(paper)),
        }))
        pushToast('Removed from workspace', 'success')
      } catch (caught) {
        pushToast(caught instanceof Error ? caught.message : 'Failed to remove paper.', 'error')
      }
    },
    [pushToast, refreshWorkspace],
  )

  const togglePaperSelection = useCallback((workspaceId: number, paper: Paper) => {
    setSelectionState((current) => {
      if (current.workspaceId !== null && current.workspaceId !== workspaceId) {
        persistSelection(workspaceId, [paper])
        return { workspaceId, papers: [paper] }
      }
      const key = paperKey(paper)
      const exists = current.papers.some((p) => paperKey(p) === key)
      const nextPapers = exists
        ? current.papers.filter((p) => paperKey(p) !== key)
        : [...current.papers, paper]
      persistSelection(workspaceId, nextPapers)
      return { workspaceId, papers: nextPapers }
    })
  }, [])

  const clearSelection = useCallback(() => {
    setSelectionState((current) => {
      if (current.workspaceId !== null) persistSelection(current.workspaceId, [])
      return { workspaceId: null, papers: [] }
    })
  }, [])

  const setSelection = useCallback((workspaceId: number, papers: Paper[]) => {
    persistSelection(workspaceId, papers)
    setSelectionState({ workspaceId, papers })
  }, [])

  const isSelected = useCallback(
    (paper: Paper) => {
      const key = paperKey(paper)
      return selection.papers.some((p) => paperKey(p) === key)
    },
    [selection.papers],
  )

  const recordBrief = useCallback(
    async (workspaceId: number, brief: BriefPayload) => {
      const created: WorkspaceBrief = await api.createBrief(workspaceId, {
        mode: brief.mode,
        style: brief.style,
        title: brief.title,
        body: brief.body,
        source_papers: brief.source_papers,
      })
      setWorkspaceDetails((current) => {
        const ex = current[workspaceId]
        if (!ex) return current
        const rest = (ex.briefs ?? []).filter((b) => b.id !== created.id)
        return { ...current, [workspaceId]: { ...ex, briefs: [created, ...rest] } }
      })
      await refreshWorkspace(workspaceId)
      setWorkspaceDetails((current) => {
        const ex = current[workspaceId]
        if (!ex || ex.briefs?.some((b) => b.id === created.id)) return current
        return { ...current, [workspaceId]: { ...ex, briefs: [created, ...(ex.briefs ?? [])] } }
      })
    },
    [refreshWorkspace],
  )

  const deleteBrief = useCallback(
    async (workspaceId: number, briefId: number) => {
      try {
        await api.deleteBrief(workspaceId, briefId)
        await refreshWorkspace(workspaceId)
        pushToast('Brief removed', 'success')
      } catch (caught) {
        pushToast(caught instanceof Error ? caught.message : 'Failed to delete brief.', 'error')
      }
    },
    [pushToast, refreshWorkspace],
  )

  const updateWorkspaceState = useCallback(
    async (workspaceId: number, key: string, value: Record<string, unknown>) => {
      try {
        await api.updateWorkspaceState(workspaceId, key, value)
        await refreshWorkspace(workspaceId)
      } catch (caught) {
        pushToast(caught instanceof Error ? caught.message : 'Failed to save workspace state.', 'error')
      }
    },
    [pushToast, refreshWorkspace],
  )

  const updatePaperNote = useCallback(
    async (workspaceId: number, paper: Paper, note: string) => {
      try {
        await api.updatePaperNote(workspaceId, paper, note)
        await refreshWorkspace(workspaceId)
        pushToast('Paper note saved', 'success')
      } catch (caught) {
        pushToast(caught instanceof Error ? caught.message : 'Failed to save paper note.', 'error')
      }
    },
    [pushToast, refreshWorkspace],
  )

  useEffect(() => {
    void refreshWorkspaces()
  }, [refreshWorkspaces])

  const value = useMemo<StoreValue>(
    () => ({
      workspaces,
      workspaceDetails,
      loadingWorkspaces,
      selection,
      toasts,
      refreshWorkspaces,
      refreshWorkspace,
      createWorkspace,
      updateWorkspace,
      deleteWorkspace,
      savePaper,
      removePaper,
      togglePaperSelection,
      clearSelection,
      setSelection,
      isSelected,
      pushToast,
      dismissToast,
      recordBrief,
      deleteBrief,
      updateWorkspaceState,
      updatePaperNote,
    }),
    [
      workspaces,
      workspaceDetails,
      loadingWorkspaces,
      selection,
      toasts,
      refreshWorkspaces,
      refreshWorkspace,
      createWorkspace,
      updateWorkspace,
      deleteWorkspace,
      savePaper,
      removePaper,
      togglePaperSelection,
      clearSelection,
      setSelection,
      isSelected,
      pushToast,
      dismissToast,
      recordBrief,
      deleteBrief,
      updateWorkspaceState,
      updatePaperNote,
    ],
  )

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}

export function useWorkspaceStore() {
  const value = useContext(StoreContext)
  if (!value) throw new Error('useWorkspaceStore must be used inside WorkspaceStoreProvider')
  return value
}
