import { Route, Routes } from 'react-router-dom';

import { RequireSession } from '@/components/RequireSession';
import LandingPage from '@/pages/LandingPage';
import LoginPage from '@/pages/LoginPage';
import MethodologyPage from '@/pages/MethodologyPage';
import PrimitivesGallery from '@/pages/PrimitivesGallery';
import WorkbenchPage from '@/pages/WorkbenchPage';

export default function App() {
  return (
    <Routes>
      {/* Marketing landing (Phase 3). CTAs route into the workbench. */}
      <Route path="/" element={<LandingPage />} />
      {/* The gate between the landing page and the product (Deploy.md D-2).
          Public by necessity, and a no-op wherever the gateway reports
          `auth_required: false`. */}
      <Route path="/login" element={<LoginPage />} />
      {/* The product (Phase 2). Guarded in the UI for the redirect only — the
          gateway is what actually refuses, on every protected route. */}
      <Route
        path="/workbench"
        element={
          <RequireSession>
            <WorkbenchPage />
          </RequireSession>
        }
      />
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
