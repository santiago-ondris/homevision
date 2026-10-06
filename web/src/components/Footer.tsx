import { authorName, sourceUrl } from "../lib/config";

export default function Footer() {
  return (
    <footer className="page-footer">
      {authorName} ·{" "}
      <a href={sourceUrl} target="_blank" rel="noreferrer">
        Source
      </a>
    </footer>
  );
}
