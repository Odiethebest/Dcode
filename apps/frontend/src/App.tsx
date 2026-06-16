import { Link, Route, Routes } from 'react-router-dom';

import ComparePage from '@/pages/ComparePage';
import IndexPage from '@/pages/IndexPage';
import QueryPage from '@/pages/QueryPage';

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-stone-50 text-stone-800">
      <header className="border-b border-stone-200 px-6 py-4 flex items-center gap-6">
        <span className="font-semibold tracking-tight">Dcode</span>
        <nav className="flex gap-4 text-sm">
          <Link to="/" className="hover:underline">
            Index
          </Link>
          <Link to="/query" className="hover:underline">
            Query
          </Link>
          <Link to="/compare" className="hover:underline">
            Compare
          </Link>
        </nav>
      </header>
      <main className="flex-1 px-6 py-8">
        <Routes>
          <Route path="/" element={<IndexPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/compare" element={<ComparePage />} />
        </Routes>
      </main>
    </div>
  );
}
