import { useEffect } from "react";
import { Film } from "lucide-react";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { EmptyState } from "./components/EmptyState";
import { OfflineBanner } from "./components/OfflineBanner";
import { PullToRefresh } from "./components/PullToRefresh";
import { RequireMember, RequirePlayer } from "./components/RequireMember";
import { Wordmark } from "./components/Wordmark";
import { buttonClass } from "./components/Button";
import { AccountPage } from "./pages/AccountPage";
import { AuthPage } from "./pages/AuthPage";
import { ForgotPasswordPage, ResetPasswordPage, VerifyEmailPage } from "./pages/EmailAuthPages";
import { GroupPage } from "./pages/group/GroupPage";
import { GroupJoinPage } from "./pages/GroupJoinPage";
import { GroupsPage } from "./pages/GroupsPage";
import { GuestStartPage } from "./pages/GuestStartPage";
import { HubPage } from "./pages/HubPage";
import { JoinPage } from "./pages/JoinPage";
import { AboutPage, PrivacyPage, TermsPage } from "./pages/LegalPage";
import { SearchPage } from "./pages/SearchPage";
import { LobbyPage } from "./pages/lobby/LobbyPage";
import { queryClient } from "./lib/query";
import { SessionProvider } from "./state/Session";
import { ToastProvider } from "./state/Toast";
import "./mobile.css";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function ShellLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

function NotFoundPage() {
  return (
    <main className="closed-room">
      <div className="closed-room-top">
        <Wordmark />
      </div>
      <EmptyState
        icon={<Film size={24} />}
        title="This page isn't in the log."
        body="The link may be old, or the page moved. The movies are still where you left them."
        action={
          <Link to="/" className={buttonClass("primary", "md")}>
            Back home
          </Link>
        }
      />
    </main>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <SessionProvider>
            <OfflineBanner />
            <PullToRefresh />
            <ScrollToTop />
            <Routes>
              <Route path="/auth" element={<AuthPage />} />
              <Route path="/login" element={<Navigate to="/auth" replace />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/privacy" element={<PrivacyPage />} />
              <Route path="/terms" element={<TermsPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/start" element={<GuestStartPage />} />
              <Route
                element={
                  <RequireMember>
                    <ShellLayout />
                  </RequireMember>
                }
              >
                <Route path="/" element={<HubPage />} />
                <Route path="/groups" element={<GroupsPage />} />
                <Route path="/groups/:id" element={<GroupPage />} />
                <Route path="/search" element={<SearchPage />} />
                <Route path="/account" element={<AccountPage />} />
              </Route>
              <Route
                path="/lobby/:id"
                element={
                  <RequirePlayer>
                    <LobbyPage />
                  </RequirePlayer>
                }
              />
              <Route
                path="/join/group/:token"
                element={
                  <RequireMember>
                    <GroupJoinPage />
                  </RequireMember>
                }
              />
              <Route path="/join/:lobbyId" element={<JoinPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </SessionProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
