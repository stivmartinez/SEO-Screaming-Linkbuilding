import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { Layout } from "./components/Layout";
import { CrawlView } from "./pages/CrawlView";
import { Home } from "./pages/Home";

function LegacyPageRedirect() {
  const { crawlId, pageId } = useParams();
  return <Navigate to={`/crawls/${crawlId}?page=${pageId}`} replace />;
}

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/crawls/:crawlId" element={<CrawlView />} />
        <Route path="/crawls/:crawlId/pages/:pageId" element={<LegacyPageRedirect />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
