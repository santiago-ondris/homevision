interface Props {
  json: string;
  copied: boolean;
  error: string | null;
  onCopy: () => void;
}

export default function JsonView({ json, copied, error, onCopy }: Props) {
  return (
    <div className="json-view">
      <button type="button" onClick={onCopy}>
        {copied ? "Copied" : "Copy"}
      </button>
      {error && <p role="alert">{error}</p>}
      <pre>{json}</pre>
    </div>
  );
}
