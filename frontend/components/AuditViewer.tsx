type AuditViewerProps = {
  items: Array<Record<string, unknown>>;
};

export function AuditViewer({ items }: AuditViewerProps) {
  return (
    <div className="card p-5">
      <p className="kicker">Audit Log</p>
      <div className="mono mt-3 max-h-64 space-y-2 overflow-auto text-xs">
        {items.length === 0 ? (
          <p className="text-text-muted">No audit events yet.</p>
        ) : (
          items.map((item, index) => (
            <pre
              key={`${String(item.ts ?? "event")}-${index}`}
              className="overflow-x-auto rounded-lg border border-border-subtle bg-bg p-2.5 text-text-secondary"
            >
              {JSON.stringify(item, null, 2)}
            </pre>
          ))
        )}
      </div>
    </div>
  );
}
