export type SourceKey = 'crossref' | 'semantic_scholar' | 'openalex' | 'pubmed' | 'arxiv'

export type Paper = {
  source: string
  external_id: string
  title: string
  abstract: string | null
  /** User-provided text; used in synthesis before catalog abstract when set. */
  abstract_override?: string | null
  authors: string[]
  venue: string | null
  year: number | null
  publication_date: string | null
  doi: string | null
  url: string | null
  pdf_url: string | null
  citation_count: number | null
  open_access: boolean | null
}

export type LibraryPaper = Paper & {
  workspace_id: number
  workspace_title: string
  saved_at: string
}

export type SearchResponse = {
  query: string
  results: Paper[]
  source_errors: Record<string, string>
}

export type SortOption = 'relevance' | 'newest' | 'most_cited'

export type CollaborationTurn = {
  role: 'user' | 'assistant'
  content: string
}

export type CollaborativeSearchPlan = {
  query: string
  sources: string[]
  limit_per_source: number
  year_from: number | null
  year_to: number | null
  open_access_only: boolean
  sort_by: SortOption
}

export type ResearchSearchCollaborateResponse = {
  phase: 'asking' | 'ready'
  assistant_message: string
  quick_replies: string[]
  search: CollaborativeSearchPlan | null
}

export type ExportResponse = {
  format: string
  content: string
}

export type ReadingPathStep = {
  order: number
  title: string
  source: string
  external_id: string
  rationale: string
}

export type ReadingPathResponse = {
  objective: string
  overview: string
  steps: ReadingPathStep[]
}

export type SearchHistory = {
  id: number
  query: string
  sources: string[]
  result_count: number
  created_at: string
}

export type WorkspaceBrief = {
  id: number
  mode: string
  style: string
  title: string
  body: string
  source_papers: Paper[]
  created_at: string
}

export type WorkspaceStateEntry = {
  state_key: string
  value: Record<string, unknown>
  updated_at: string
}

export type PaperNote = {
  source: string
  external_id: string
  note: string
  updated_at: string
}

export type WorkspaceSummary = {
  id: number
  title: string
  notes: string
  saved_paper_count: number
  search_count: number
  created_at: string
  updated_at: string
}

export type WorkspaceDetail = WorkspaceSummary & {
  saved_papers: Paper[]
  searches: SearchHistory[]
  briefs: WorkspaceBrief[]
  state: WorkspaceStateEntry[]
  paper_notes: PaperNote[]
}

export const SOURCE_OPTIONS: Array<{ key: SourceKey; label: string; tone: string }> = [
  { key: 'semantic_scholar', label: 'Semantic Scholar', tone: 'tone-rose' },
  { key: 'openalex', label: 'OpenAlex', tone: 'tone-teal' },
  { key: 'crossref', label: 'Crossref', tone: 'tone-amber' },
  { key: 'pubmed', label: 'PubMed', tone: 'tone-violet' },
  { key: 'arxiv', label: 'arXiv', tone: 'tone-red' },
]

export const ALL_SOURCE_KEYS = SOURCE_OPTIONS.map((option) => option.key)

export function isSourceKey(value: string): value is SourceKey {
  return (ALL_SOURCE_KEYS as readonly string[]).includes(value)
}

export const paperKey = (paper: Pick<Paper, 'source' | 'external_id'>) =>
  `${paper.source}::${paper.external_id}`
