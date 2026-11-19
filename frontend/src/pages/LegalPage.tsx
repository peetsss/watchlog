import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "../components/Wordmark";
import { usePageTitle } from "../lib/usePageTitle";
import "./legal.css";

const CONTACT_EMAIL = "hello@watchlog.example";

function LegalLayout({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <main className="legal-page">
      <header className="legal-top">
        <Wordmark />
        <Link to="/" className="text-link legal-back">
          <ArrowLeft size={15} aria-hidden="true" /> Back home
        </Link>
      </header>
      <article className="legal-card">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="display legal-title">{title}</h1>
        <div className="legal-body">{children}</div>
      </article>
    </main>
  );
}

export function AboutPage() {
  usePageTitle("About & credits");

  return (
    <LegalLayout eyebrow="About watchlog" title="A quieter place for movie people.">
      <p>
        watchlog is a shared watchlist, a club scoreboard and a real-time movie-night
        lobby. It is built for the people who stay for the credits, not for another
        endless group chat.
      </p>

      <h2>How it works</h2>
      <p>
        Create a group, add movies, score what you watch and open a room when it is
        time to choose. A room asks everyone to ready up, votes movie by movie, then
        lets the finalists settle it with one pick each.
      </p>

      <h2>Data &amp; credits</h2>
      <div className="legal-credit">
        <img className="legal-credit-logo" src="/brand/tmdb-logo.svg" alt="TMDB" />
        <div>
          <p>
            This product uses the TMDB API but is not endorsed or certified by TMDB.
          </p>
          <p>
            Movie metadata, posters and backdrops come from{" "}
            <a href="https://www.themoviedb.org" target="_blank" rel="noopener">
              The Movie Database (TMDB)
            </a>
            .
          </p>
        </div>
      </div>
      <p>
        Watch availability data, when shown, is provided by{" "}
        <a href="https://www.justwatch.com/pl" target="_blank" rel="noopener">
          JustWatch
        </a>
        . Availability varies by country and can change.
      </p>

      <h2>Contact</h2>
      <p>
        Questions, corrections or a broken invite? Write to{" "}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </LegalLayout>
  );
}

export function PrivacyPage() {
  usePageTitle("Privacy");

  return (
    <LegalLayout eyebrow="Privacy" title="What we keep, and why.">
      <p>
        This page describes the information watchlog needs to run the product. It is
        a plain-language summary, not a substitute for the full privacy notice that
        will be published before launch.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li>Account details: username, email address and password hash.</li>
        <li>
          Product activity: groups, watchlists, scores, lobby votes, picks and
          invitations.
        </li>
        <li>
          Technical data: request logs, IP address and error reports used to keep the
          service secure and working.
        </li>
      </ul>

      <h2>How we use it</h2>
      <ul>
        <li>To sign you in, run your groups and show the right room to the right people.</li>
        <li>To send transactional email such as verification and password resets.</li>
        <li>To prevent abuse, investigate errors and keep the service available.</li>
      </ul>

      <h2>Who processes it</h2>
      <p>
        We use service providers for hosting, database and Redis infrastructure, and
        transactional email delivery. Movie metadata and images come from TMDB. Watch
        availability, when shown, comes from JustWatch via TMDB. We do not sell
        personal data.
      </p>

      <h2>Cookies</h2>
      <p>
        watchlog uses essential session and CSRF cookies. We do not use advertising
        cookies or third-party tracking cookies.
      </p>

      <h2>Your choices</h2>
      <p>
        You can export your account data from account settings. To request deletion
        or correction, contact{" "}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. Guest sessions and
        abandoned rooms expire automatically.
      </p>

      <h2>Retention</h2>
      <p>
        Account data is kept while your account is active. Guest sessions, invite
        tokens and operational logs are kept only as long as needed for security and
        normal operation.
      </p>
    </LegalLayout>
  );
}

export function TermsPage() {
  usePageTitle("Terms");

  return (
    <LegalLayout eyebrow="Terms" title="The house rules.">
      <p>
        These are the basic rules for using watchlog. The full terms will be
        published before launch.
      </p>

      <h2>Your account</h2>
      <p>
        Keep your credentials private and use an email address you control. You are
        responsible for activity under your account. Do not impersonate another
        person or create accounts to abuse the service.
      </p>

      <h2>Your groups</h2>
      <p>
        Group names, watchlists, scores and invitations are created by members. Only
        share an invite with people you want in the group. Do not use watchlog to
        harass people or publish content you do not have the right to share.
      </p>

      <h2>Movie data and availability</h2>
      <p>
        Movie data and imagery are provided by TMDB. Watch availability, when shown,
        is provided by JustWatch and can change. watchlog does not guarantee that a
        title is available on a particular service or in a particular country.
      </p>

      <h2>Availability of the service</h2>
      <p>
        watchlog is provided as-is while it is being built and operated. Features may
        change, and rooms or guest sessions may expire. We may suspend accounts that
        abuse the service or break these rules.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about these terms? Write to{" "}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </LegalLayout>
  );
}
