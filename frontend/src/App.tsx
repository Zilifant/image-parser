import { Navigate, Route, Routes } from 'react-router-dom'

import EditorPage from './pages/EditorPage'
import LibraryPage from './pages/LibraryPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LibraryPage />} />
      <Route path="/projects/:projectId" element={<LibraryPage />} />
      <Route path="/projects/:projectId/pages/:pageId" element={<EditorPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
