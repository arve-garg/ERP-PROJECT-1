import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "../../app/auth-context";
import { apiRequest } from "../../lib/api";
import type { Paginated } from "../../lib/types";

interface SearchResult {
  entity: string;
  id: number;
  display_name: string;
}

export function GlobalSearch() {
  const { accessToken } = useAuth();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  const results = useQuery({
    queryKey: ["global-search", debounced],
    queryFn: () =>
      apiRequest<Paginated<SearchResult>>(
        `/search/?q=${encodeURIComponent(debounced)}&page_size=8`,
        {},
        accessToken,
      ),
    enabled: debounced.length >= 2,
  });

  return (
    <div className="global-search">
      <Search size={16} aria-hidden="true" />
      <input
        aria-label="Search workspace"
        aria-expanded={open && debounced.length >= 2}
        aria-controls="search-results"
        placeholder="Search workspace"
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
      />
      {open && debounced.length >= 2 && (
        <div className="search-results" id="search-results" role="listbox">
          {results.isPending && (
            <p className="search-state" role="status">
              Searching…
            </p>
          )}
          {results.isError && (
            <p className="search-state search-error" role="alert">
              Search is unavailable right now.
            </p>
          )}
          {results.isSuccess && results.data.results.length === 0 && (
            <p className="search-state">No matches found.</p>
          )}
          {results.isSuccess &&
            results.data.results.map((item) => (
              <button
                type="button"
                role="option"
                aria-selected="false"
                key={`${item.entity}-${item.id}`}
                onClick={() => {
                  setQuery(item.display_name);
                  setOpen(false);
                }}
              >
                <span className="search-result-type">{item.entity}</span>
                {item.display_name}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
