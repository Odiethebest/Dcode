import { Route, Routes } from 'react-router-dom';

import ComparePage from '@/pages/ComparePage';
import IndexPage from '@/pages/IndexPage';
import LandingPage from '@/pages/LandingPage';
import MethodologyPage from '@/pages/MethodologyPage';
import PrimitivesGallery from '@/pages/PrimitivesGallery';
import QueryPage from '@/pages/QueryPage';
import WorkbenchPage from '@/pages/WorkbenchPage';

export default function App() {
  return (
    <Routes>
      {/* Marketing landing (Phase 3). CTAs route into the workbench. */}
      <Route path="/" element={<LandingPage />} />
      {/* The product (Phase 2). */}
      <Route path="/workbench" element={<WorkbenchPage />} />
      {/* Evaluation / H1 story, moved out of the product (Phase 3 slice 3b). */}
      <Route path="/methodology" element={<MethodologyPage />} />
      {/* Design-system gallery (Phase 1). */}
      <Route path="/preview" element={<PrimitivesGallery />} />
      {/* Legacy tab IA — off-nav, kept reachable until Phase 4 retires it. */}
      <Route path="/legacy/index" element={<IndexPage />} />
      <Route path="/legacy/query" element={<QueryPage />} />
      <Route path="/legacy/compare" element={<ComparePage />} />
    </Routes>
  );
}
