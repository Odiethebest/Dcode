import { Route, Routes } from 'react-router-dom';

import LandingPage from '@/pages/LandingPage';
import MethodologyPage from '@/pages/MethodologyPage';
import PrimitivesGallery from '@/pages/PrimitivesGallery';
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
      {/* The pre-rebuild Index/Query/Compare tab IA was retired in Phase 4 —
          deleted rather than redirected: nothing linked to it, and the pages
          were still on the pre-token palette. */}
    </Routes>
  );
}
