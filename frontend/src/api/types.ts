export type SourceKey = 'crossref' | 'semantic_scholar' | 'openalex' | 'pubmed' | 'arxiv'

export type Paper = {
  source: string
  external_id: string
  title: string
  abstract: string | null
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
}

export const SOURCE_OPTIONS: Array<{ key: SourceKey; label: string; tone: string }> = [
  { key: 'semantic_scholar', label: 'Semantic Scholar', tone: 'tone-rose' },
  { key: 'openalex', label: 'OpenAlex', tone: 'tone-teal' },
  { key: 'crossref', label: 'Crossref', tone: 'tone-amber' },
  { key: 'pubmed', label: 'PubMed', tone: 'tone-violet' },
  { key: 'arxiv', label: 'arXiv', tone: 'tone-red' },
]

export const ALL_SOURCE_KEYS = SOURCE_OPTIONS.map((option) => option.key)

export const paperKey = (paper: Pick<Paper, 'source' | 'external_id'>) =>
  `${paper.source}::${paper.external_id}`
