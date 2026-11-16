import { useEffect } from "react";
import { Film } from "lucide-react";
import {
  BrowserRouter,
  Link,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { EmptyState } from "./components/EmptyState";
import { MemberOnly } from "./components/MemberOnly";
import { OfflineBanner } from "./components/OfflineBanner";
import { Wordmark } from "./components/Wordmark";
import { buttonClass } from "./components/Button";
import { GroupPage } from "./pages/group/GroupPage";
import { GroupsPage } from "./pages/GroupsPage";
import { HubPage } from "./pages/HubPage";
import { JoinPage } from "./pages/JoinPage";
import { SearchPage } from "./pages/SearchPage";
import { LobbyPage } from "./pages/lobby/LobbyPage";
import { GroupsProvider } from "./state/Groups";
import { GuestGateProvider } from "./state/GuestGate";
import { LobbyProvider } from "./state/Lobby";
import { ToastProvider } from "./state/Toast";
import { ViewerProvider } from "./state/Viewer";
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
        body="The link may be old, or the page moved. The films are still where you left them."
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
    <BrowserRouter>
      <ToastProvider>
        <ViewerProvider>
          <GroupsProvider>
            <LobbyProvider>
              <GuestGateProvider>
                <OfflineBanner />
                <ScrollToTop />
                <Routes>
                  <Route element={<ShellLayout />}>
                    <Route path="/" element={<HubPage />} />
                    <Route
                      path="/groups"
                      element={
                        <MemberOnly>
                          <GroupsPage />
                        </MemberOnly>
                      }
                    />
                    <Route
                      path="/groups/:id"
                      element={
                        <MemberOnly>
                          <GroupPage />
                        </MemberOnly>
                      }
                    />
                    <Route path="/search" element={<SearchPage />} />
                  </Route>
                  <Route path="/lobby/:id" element={<LobbyPage />} />
                  <Route path="/join/:code" element={<JoinPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </GuestGateProvider>
            </LobbyProvider>
          </GroupsProvider>
        </ViewerProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
