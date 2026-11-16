import { Home, LogOut, Search, UserRound, Users } from "lucide-react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { stageLabel } from "../data";
import { useGroupList } from "../lib/api-groups";
import { cx } from "../lib/cx";
import { useLobby } from "../state/Lobby";
import { useSession } from "../state/Session";
import { Avatar } from "./Avatar";
import { Wordmark } from "./Wordmark";

const navItems = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/groups", label: "Groups", icon: Users, end: false },
  { to: "/search", label: "Search", icon: Search, end: false },
];

const groupTones = ["#e7b45a", "#9bb39a", "#8fa6bf", "#d09a83"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const groups = useGroupList().data ?? [];
  const { lobby, resetLobby } = useLobby();
  const { person, signOut } = useSession();
  const navigate = useNavigate();

  const handleSignOut = () => {
    void signOut().finally(() => {
      resetLobby();
      navigate("/auth", { replace: true });
    });
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside className="sidebar">
        <div className="sidebar-top">
          <Wordmark />
        </div>

        <nav className="side-nav" aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => cx("side-nav-link", isActive && "is-active")}
              >
                <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {lobby && lobby.stage !== "winner" ? (
          <Link to="/lobby/friday" className="side-live">
            <span className="live-dot" aria-hidden="true" />
            <span className="side-live-copy">
              <strong>Movie night in progress</strong>
              <span>{stageLabel(lobby)}</span>
            </span>
          </Link>
        ) : null}

        <div className="side-groups">
          <div className="side-label">
            <span>Your groups</span>
            <Link to="/groups" className="side-label-link" aria-label="View all groups">
              All
            </Link>
          </div>
          {groups.slice(0, 4).map((group, index) => (
            <Link key={group.id} to={`/groups/${group.id}`} className="side-group">
              <span
                className="side-group-dot"
                style={{ background: groupTones[index % groupTones.length] }}
                aria-hidden="true"
              />
              <span>{group.name}</span>
            </Link>
          ))}
        </div>

        <div className="sidebar-foot">
          <div className="side-user">
            {person ? (
              <Avatar person={person} size={34} />
            ) : (
              <span className="side-anon-avatar" aria-hidden="true">
                <UserRound size={18} />
              </span>
            )}
            <div>
              <strong>{person?.name ?? "Member"}</strong>
              <span>Member</span>
            </div>
            <button
              type="button"
              className="side-signout"
              onClick={handleSignOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={15} />
            </button>
          </div>
          <p className="side-note">A quieter place for movie people.</p>
        </div>
      </aside>

      <div className="app-main">
        <header className="mobile-top">
          <Wordmark />
          <div className="mobile-top-actions">
            {person ? (
              <Avatar person={person} size={32} />
            ) : (
              <span className="side-anon-avatar" aria-hidden="true">
                <UserRound size={17} />
              </span>
            )}
            <button
              type="button"
              className="mobile-icon-button"
              onClick={handleSignOut}
              aria-label="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <main id="main" className="page">
          {children}
        </main>

        <nav className="bottom-nav" aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => cx("bottom-nav-link", isActive && "is-active")}
              >
                <Icon size={20} strokeWidth={1.8} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
