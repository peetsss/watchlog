import { Home, LogOut, Search, UserPlus, UserRound, Users } from "lucide-react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { stageLabel } from "../data";
import { cx } from "../lib/cx";
import { useGroups } from "../state/Groups";
import { useGuestGate } from "../state/GuestGate";
import { useLobby } from "../state/Lobby";
import { useViewer } from "../state/Viewer";
import { Avatar } from "./Avatar";
import { Wordmark } from "./Wordmark";

const navItems = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/groups", label: "Groups", icon: Users, end: false },
  { to: "/search", label: "Search", icon: Search, end: false },
];

const groupTones = ["#e7b45a", "#9bb39a", "#8fa6bf", "#d09a83"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { groups } = useGroups();
  const { lobby, resetLobby } = useLobby();
  const { isMember, person, signOut } = useViewer();
  const { openAccount } = useGuestGate();
  const navigate = useNavigate();
  const items = isMember ? navItems : navItems.filter((item) => item.to !== "/groups");

  const handleSignOut = () => {
    signOut();
    resetLobby();
    navigate("/");
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
          {items.map((item) => {
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
            {isMember ? (
              <Link to="/groups" className="side-label-link" aria-label="View all groups">
                All
              </Link>
            ) : null}
          </div>
          {isMember ? (
            groups.slice(0, 4).map((group, index) => (
              <Link key={group.id} to={`/groups/${group.id}`} className="side-group">
                <span
                  className="side-group-dot"
                  style={{ background: groupTones[index % groupTones.length] }}
                  aria-hidden="true"
                />
                <span>{group.name}</span>
              </Link>
            ))
          ) : (
            <p className="side-guest-note">
              No clubs yet. Create an account to join one, or keep playing as a guest.
            </p>
          )}
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
              <strong>{person?.name ?? "Not signed in"}</strong>
              <span>{isMember ? "Signed in" : person ? "Guest" : "Guest access"}</span>
            </div>
            {isMember ? (
              <button
                type="button"
                className="side-signout"
                onClick={handleSignOut}
                aria-label="Sign out"
                title="Sign out"
              >
                <LogOut size={15} />
              </button>
            ) : (
              <button
                type="button"
                className="side-signout"
                onClick={openAccount}
                aria-label="Create an account"
                title="Create an account"
              >
                <UserPlus size={15} />
              </button>
            )}
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
            {isMember ? (
              <button
                type="button"
                className="mobile-icon-button"
                onClick={handleSignOut}
                aria-label="Sign out"
              >
                <LogOut size={16} />
              </button>
            ) : (
              <button
                type="button"
                className="mobile-icon-button"
                onClick={openAccount}
                aria-label="Create an account"
              >
                <UserPlus size={16} />
              </button>
            )}
          </div>
        </header>

        <main id="main" className="page">
          {children}
        </main>

        <nav className="bottom-nav" aria-label="Primary">
          {items.map((item) => {
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
