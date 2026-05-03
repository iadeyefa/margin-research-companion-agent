import type {
  ExportResponse,
  LibraryPaper,
  Paper,
  ReadingPathResponse,
  SearchResponse,
  SortOption,
  SourceKey,
  WorkspaceDetail,
  WorkspaceSummary,
} from './types'

const API_URL = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`
  let response: Response
  try {
    response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
      ...init,
    })
  } catch (err) {
    const hint =
      API_URL === ''
        ? ' Start the API on port 3000 (e.g. uvicorn in backend/) so the Vite /api proxy can reach it.'
        : ` This app’s API runs on port 3000 by default (not 8000). Set VITE_API_URL=http://localhost:3000 or remove it to use the dev proxy. Current: ${API_URL}`
    const reason = err instanceof Error ? err.message : 'Network error'
    throw new ApiError(
      reason === 'Load failed' || reason === 'Failed to fetch'
        ? `Cannot reach the API.${hint}`
        : `${reason}.${hint}`,
      0,
    )
  }

  if (!response.ok) {
    const message = await response.text()
    throw new ApiError(message || `Request failed with status ${response.status}`, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

export const api = {
  listWorkspaces: () => requestJson<WorkspaceSummary[]>('/api/workspaces/'),
  createWorkspace: (title: string) =>
    requestJson<WorkspaceDetail>('/api/workspaces/', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  getWorkspace: (id: number) => requestJson<WorkspaceDetail>(`/api/workspaces/${id}`),
  updateWorkspace: (id: number, payload: { title?: string; notes?: string }) =>
    requestJson<WorkspaceSummary>(`/api/workspaces/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteWorkspace: (id: number) =>
    requestJson<{ message: string }>(`/api/workspaces/${id}`, { method: 'DELETE' }),
  savePaper: (workspaceId: number, paper: Paper) =>
    requestJson<Paper>(`/api/workspaces/${workspaceId}/papers`, {
      method: 'POST',
      body: JSON.stringify(paper),
    }),
  removePaper: (workspaceId: number, source: string, externalId: string) =>
    requestJson<{ message: string }>(
      `/api/workspaces/${workspaceId}/papers/${encodeURIComponent(source)}/${encodeURIComponent(externalId)}`,
      { method: 'DELETE' },
    ),
  patchSavedPaper: (
    workspaceId: number,
    source: string,
    externalId: string,
    payload: { abstract_override?: string | null },
  ) =>
    requestJson<Paper>(
      `/api/workspaces/${workspaceId}/papers/${encodeURIComponent(source)}/${encodeURIComponent(externalId)}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
    ),
  search: (payload: {
    query: string
    limit_per_source: number
    sources: SourceKey[]
    workspace_id: number | null
    year_from: number | null
    year_to: number | null
    open_access_only: boolean
    sort_by: SortOption
  }) =>
    requestJson<SearchResponse>('/api/research/search', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  synthesize: (payload: {
    mode: 'summary' | 'compare' | 'question'
    question: string | null
    papers: Paper[]
  }) =>
    requestJson<{ response: string; mode: string }>('/api/research/synthesize', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  buildReadingPath: (payload: { objective: string | null; papers: Paper[] }) =>
    requestJson<ReadingPathResponse>('/api/research/reading-path', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  exportPapers: (payload: { format: 'bibtex' | 'markdown'; papers: Paper[] }) =>
    requestJson<ExportResponse>('/api/research/export', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listLibrary: () => requestJson<LibraryPaper[]>('/api/library/papers'),
}
