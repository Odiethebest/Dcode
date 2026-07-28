import { Route, Routes } from 'react-router-dom';

import ComparePage from '@/pages/ComparePage';
import IndexPage from '@/pages/IndexPage';
import PrimitivesGallery from '@/pages/PrimitivesGallery';
import QueryPage from '@/pages/QueryPage';
import WorkbenchPage from '@/pages/WorkbenchPage';

export default function App() {
  return (
    <Routes>
      {/* The workbench is the product (Phase 2). It owns its own full-screen chrome. */}
      <Route path="/" element={<WorkbenchPage />} />
      {/* Design-system gallery (Phase 1). */}
      <Route path="/preview" element={<PrimitivesGallery />} />
      {/* Legacy tab IA — off-nav, kept reachable until Phase 4 retires it. */}
      <Route path="/legacy/index" element={<IndexPage />} />
      <Route path="/legacy/query" element={<QueryPage />} />
      <Route path="/legacy/compare" element={<ComparePage />} />
    </Routes>
  );
}
