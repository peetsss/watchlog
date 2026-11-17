import { ExternalLink, Tv } from "lucide-react";
import type { WatchAvailabilityView, WatchProviderView } from "../lib/adapters";

const JUSTWATCH_PATHS: Record<string, string> = {
  GB: "uk",
  US: "us",
  PL: "pl",
};

const GROUP_LABELS: Record<keyof WatchAvailabilityView["offers"], string> = {
  flatrate: "Included with subscriptions",
  free: "Free",
  ads: "With ads",
  rent: "Rent",
  buy: "Buy",
};

function justWatchUrl(region: string): string {
  const path = JUSTWATCH_PATHS[region] ?? region.toLowerCase();
  return `https://www.justwatch.com/${path}`;
}

function regionName(region: string): string {
  if (region === "PL") return "Poland";
  if (region === "US") return "the US";
  if (region === "GB") return "the UK";
  return region;
}

function ProviderChip({ provider }: { provider: WatchProviderView }) {
  return (
    <span className="watch-provider" title={provider.name}>
      {provider.logoUrl ? (
        <img src={provider.logoUrl} alt="" loading="lazy" />
      ) : (
        <span className="watch-provider-fallback" aria-hidden="true">
          {provider.name.slice(0, 1)}
        </span>
      )}
      <span>{provider.name}</span>
    </span>
  );
}

export function WhereToWatch({
  watch,
  compact = false,
}: {
  watch: WatchAvailabilityView | null;
  compact?: boolean;
}) {
  if (!watch) {
    return compact ? null : (
      <section className="detail-section watch-section">
        <h3>Where to watch</h3>
        <p className="detail-muted">Where to watch is temporarily unavailable.</p>
      </section>
    );
  }

  const grouped = (Object.keys(GROUP_LABELS) as Array<keyof WatchAvailabilityView["offers"]>).filter(
    (type) => watch.offers[type].length > 0,
  );
  const flat = [...watch.offers.flatrate, ...watch.offers.free];
  const fallback = watch.offers.rent.length ? watch.offers.rent : watch.offers.buy;
  const compactProviders = (flat.length ? flat : fallback).slice(0, 3);
  const justwatch = justWatchUrl(watch.region);

  if (compact) {
    if (!compactProviders.length) return null;
    return (
      <div className="watch-compact">
        <span className="watch-compact-label">Where to watch</span>
        <span className="watch-compact-providers">
          {compactProviders.map((provider) => (
            <ProviderChip key={`${provider.id}-${provider.name}`} provider={provider} />
          ))}
        </span>
        <a
          className="watch-source-link"
          href={justwatch}
          target="_blank"
          rel="noopener"
          aria-label="Watch options by JustWatch"
        >
          via JustWatch
        </a>
      </div>
    );
  }

  return (
    <section className="detail-section watch-section">
      <div className="watch-heading">
        <h3>Where to watch</h3>
        <span className="watch-region">{regionName(watch.region)}</span>
      </div>

      {grouped.length ? (
        <div className="watch-groups">
          {grouped.map((type) => (
            <div className="watch-group" key={type}>
              <span className="watch-group-label">{GROUP_LABELS[type]}</span>
              <div className="watch-providers">
                {watch.offers[type].map((provider) => (
                  <ProviderChip key={`${type}-${provider.id}-${provider.name}`} provider={provider} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="detail-muted">
          <Tv size={14} aria-hidden="true" /> Not streaming in {regionName(watch.region)} right now.
        </p>
      )}

      <div className="watch-attribution">
        <a href={justwatch} target="_blank" rel="noopener">
          Watch options by JustWatch <ExternalLink size={12} aria-hidden="true" />
        </a>
        {watch.link ? (
          <a href={watch.link} target="_blank" rel="noopener">
            See all on TMDB <ExternalLink size={12} aria-hidden="true" />
          </a>
        ) : null}
      </div>
      <p className="watch-disclaimer">Availability can change.</p>
    </section>
  );
}
