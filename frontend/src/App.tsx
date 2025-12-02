import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AuthProvider } from "./context/AuthContext";
import { ScopeProvider } from "./context/ScopeContext";
import { ThemeProvider } from "./context/ThemeContext";
import { AboutPage } from "./pages/AboutPage";
import { AccessPage } from "./pages/AccessPage";
import { CatalogPage } from "./pages/CatalogPage";
import { CreatePage } from "./pages/CreatePage";
import { MyResourcesPage } from "./pages/MyResourcesPage";
import { ResourcePage } from "./pages/ResourcePage";
import { SearchPage } from "./pages/SearchPage";

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ScopeProvider>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/search" replace />} />
              <Route path="search" element={<SearchPage />} />
              <Route path="catalog" element={<CatalogPage />} />
              <Route
                path="projects/:projectId"
                element={<CatalogPage />}
              />
              <Route path="create" element={<CreatePage />} />
              <Route path="resources/:versionId" element={<ResourcePage />} />
              <Route path="my" element={<MyResourcesPage />} />
              <Route path="access" element={<AccessPage />} />
              <Route path="about" element={<AboutPage />} />
            </Route>
          </Routes>
        </ScopeProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
