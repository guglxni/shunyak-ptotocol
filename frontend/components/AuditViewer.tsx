type AuditViewerProps = {
  items: Array<Record<string, unknown>>;
};

export function AuditViewer({ items }: AuditViewerProps) {
  return (
    <div className="panel p-4">
      <p className="kicker">Audit Log</p>
      <div className="mono mt-3 max-h-64 space-y-2 overflow-auto text-xs">
        {items.length === 0 ? (
          <p className="text-fog">No audit events yet.</p>
        ) : (
          items.map((item, index) => (
            <pre
              key={`${String(item.ts ?? "event")}-${index}`}
              className="overflow-x-auto rounded-lg bg-black/30 p-2 text-fog"
            >
              {JSON.stringify(item, null, 2)}
            </pre>
          ))
        )}
      </div>
    </div>
  );
}
