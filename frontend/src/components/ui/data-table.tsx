import { EmptyState } from "@/src/components/ui/states";

export type Column<T> = {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  align?: "right" | "left";
  cellClassName?: string;
  headerClassName?: string;
};

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  emptyLabel,
  onRowClick,
  rowClassName
}: {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => React.Key;
  emptyLabel?: string;
  onRowClick?: (row: T) => void;
  rowClassName?: string;
}) {
  if (!rows.length) {
    return <EmptyState label={emptyLabel} />;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={[column.align === "right" ? "align-right" : "", column.headerClassName || ""].filter(Boolean).join(" ")}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={getRowKey(row)}
              className={`${onRowClick ? "row-clickable" : ""}${rowClassName ? ` ${rowClassName}` : ""}`}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={onRowClick ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onRowClick(row);
                }
              } : undefined}
              role={onRowClick ? "button" : undefined}
              tabIndex={onRowClick ? 0 : undefined}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  data-label={column.header}
                  className={[
                    column.align === "right" ? "align-right" : "",
                    column.cellClassName || "",
                  ].filter(Boolean).join(" ")}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
