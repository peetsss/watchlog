import { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Film,
  Plus,
  Users,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { AvatarStack } from "../components/Avatar";
import { Button } from "../components/Button";
import { CreateGroupDialog } from "../components/CreateGroupDialog";
import { EmptyState } from "../components/EmptyState";
import { PosterStack } from "../components/PosterStack";
import type { Group } from "../data";
import { usePageTitle } from "../lib/usePageTitle";
import { useGroups } from "../state/Groups";
import { useLobby } from "../state/Lobby";

export function GroupsPage() {
  usePageTitle("Groups");
  const { groups } = useGroups();
  const { startLobby } = useLobby();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);

  const handleStart = (group: Group) => {
    startLobby(group);
    navigate("/lobby/friday");
  };

  return (
    <div className="page-inner groups-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Your crews</p>
          <h1 className="display page-title">Groups</h1>
          <p className="lede page-lede">
            The people you watch with, and everything you've watched together.
          </p>
        </div>
        <Button variant="secondary" onClick={() => setCreateOpen(true)}>
          <Plus size={16} /> Create a group
        </Button>
      </header>

      <div className="groups-layout">
        <div>
          {groups.length ? (
            <div className="group-list">
              {groups.map((group) => (
                <article className="group-row" key={group.id}>
                  <PosterStack movies={group.watchlist} className="group-row-posters" />
                  <div className="group-row-body">
                    <div className="group-row-top">
                      <div>
                        <Link to={`/groups/${group.id}`} className="group-name-link">
                          <h2 className="display">{group.name}</h2>
                        </Link>
                        <p>{group.description}</p>
                      </div>
                      <Button size="sm" onClick={() => handleStart(group)}>
                        Start a night <ArrowRight size={15} />
                      </Button>
                    </div>
                    <div className="group-row-meta">
                      <span className="meta-item">
                        <AvatarStack people={group.members} size={24} />
                        {group.members.length} {group.members.length === 1 ? "member" : "members"}
                      </span>
                      <span className="meta-item">
                        <Film size={14} aria-hidden="true" />
                        {group.films.length} {group.films.length === 1 ? "film" : "films"}
                      </span>
                      <span className="meta-item">
                        <CalendarDays size={14} aria-hidden="true" />
                        {group.lastNight
                          ? `Last night: ${group.lastNight.movie.title} · ${group.lastNight.date}`
                          : "No nights yet"}
                      </span>
                      <Link to={`/groups/${group.id}`} className="meta-item group-open-link">
                        Open watchlist <ArrowUpRight size={12} />
                      </Link>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Users size={24} />}
              title="No groups yet."
              body="A group is just the people you keep coming back to. Make one, then start a room."
              action={
                <Button onClick={() => setCreateOpen(true)}>
                  <Plus size={16} /> Create a group
                </Button>
              }
            />
          )}
        </div>

        <aside className="groups-aside">
          <div className="aside-card">
            <span className="section-kicker">How a night works</span>
            <h2 className="display aside-title">Three steps, one pick.</h2>
            <ol className="steps">
              <li>
                <span className="step-number">01</span>
                <div>
                  <strong>Open a room</strong>
                  <p>Pick a crew or share an open link. Everyone readies up.</p>
                </div>
              </li>
              <li>
                <span className="step-number">02</span>
                <div>
                  <strong>Everyone votes</strong>
                  <p>A film needs a unanimous yes to reach the shortlist.</p>
                </div>
              </li>
              <li>
                <span className="step-number">03</span>
                <div>
                  <strong>The room picks</strong>
                  <p>One film wins. It lands in the watchlist for next time.</p>
                </div>
              </li>
            </ol>
          </div>

          <div className="aside-note">
            <span className="aside-note-icon" aria-hidden="true">
              <Users size={18} />
            </span>
            <p>
              <strong>No group yet?</strong> Start an open room from Home and keep the crew after.
            </p>
            <Link to="/" className="text-link">
              Go home <ArrowUpRight size={14} />
            </Link>
          </div>
        </aside>
      </div>

      <CreateGroupDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
