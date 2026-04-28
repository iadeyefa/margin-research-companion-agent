import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import './styles/app.css'
import { AppShell } from './components/AppShell'
import { DashboardPage } from './pages/Dashboard'
import { LibraryPage } from './pages/Library'
import { PaperDetailPage } from './pages/PaperDetail'
import { HistoryTab } from './pages/workspace/History'
import { NotesTab } from './pages/workspace/Notes'
import { OverviewTab } from './pages/workspace/Overview'
import { ReadingPathTab } from './pages/workspace/ReadingPath'
import { SavedTab } from './pages/workspace/Saved'
import { SearchTab } from './pages/workspace/Search'
import { SynthesisTab } from './pages/workspace/Synthesis'
import { WorkspaceLayout } from './pages/workspace/WorkspaceLayout'
import { ThemeProvider } from './state/ThemeProvider'
import { WorkspaceStoreProvider } from './state/WorkspaceStore'

function App() {
  return (
    <Router>
      <ThemeProvider>
        <WorkspaceStoreProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="library" element={<LibraryPage />} />
            <Route path="papers/:source/:externalId" element={<PaperDetailPage />} />
            <Route path="workspaces/:workspaceId" element={<WorkspaceLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<OverviewTab />} />
              <Route path="search" element={<SearchTab />} />
              <Route path="saved" element={<SavedTab />} />
              <Route path="synthesis" element={<SynthesisTab />} />
              <Route path="reading-path" element={<ReadingPathTab />} />
              <Route path="notes" element={<NotesTab />} />
              <Route path="history" element={<HistoryTab />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
        </WorkspaceStoreProvider>
      </ThemeProvider>
    </Router>
  )
}

export default App
