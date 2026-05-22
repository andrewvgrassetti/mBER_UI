import { Routes, Route, Link } from "react-router-dom";
import JobSubmitPage from "./pages/JobSubmitPage";
import DashboardPage from "./pages/DashboardPage";
import ResultsPage from "./pages/ResultsPage";
import SettingsPage from "./pages/SettingsPage";

function App() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b bg-card">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-2">
              <span className="text-xl font-bold text-primary">mBER</span>
              <span className="text-sm text-muted-foreground">
                VHH Nanobody Designer
              </span>
            </div>
            <div className="flex space-x-4">
              <Link
                to="/"
                className="px-3 py-2 rounded-md text-sm font-medium hover:bg-accent"
              >
                New Job
              </Link>
              <Link
                to="/dashboard"
                className="px-3 py-2 rounded-md text-sm font-medium hover:bg-accent"
              >
                Dashboard
              </Link>
              <Link
                to="/settings"
                className="px-3 py-2 rounded-md text-sm font-medium hover:bg-accent"
              >
                Settings
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<JobSubmitPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/jobs/:jobId/results" element={<ResultsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
