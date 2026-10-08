import { sourceUrl } from "../lib/config";
import type { KnownIssue } from "../lib/state";

interface Props {
  issues: KnownIssue[];
}

export default function KnownIssues({ issues }: Props) {
  return (
    <div className="known-issues">
      <p className="known-issues-caption">Known issues</p>
      {issues.map((issue, index) => (
        <button
          key={index}
          type="button"
          onClick={(event) => {
            const marker = event.currentTarget
              .closest(".app")
              ?.querySelector(`[data-issue-index="${index}"]`);
            marker?.scrollIntoView({
              block: "center",
              inline: "center",
              behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                ? "instant"
                : "smooth",
            });
          }}
        >
          {issue.text}
        </button>
      ))}
      <a
        href={`${sourceUrl}/blob/main/WRITEUP.md#known-limitations`}
        target="_blank"
        rel="noreferrer"
      >
        Details in the writeup
      </a>
    </div>
  );
}
