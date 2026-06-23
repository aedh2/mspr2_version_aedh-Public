import { Button } from "@/src/components/ui/button";
import type { PaginationMeta } from "@/src/types/domain";

export function Pagination({
  meta,
  page,
  onPageChange
}: {
  meta?: PaginationMeta;
  page: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = meta?.totalPages || meta?.pages || meta?.total_pages || 1;
  const total = meta?.total || 0;
  return (
    <div className="pagination">
      <span>
        Page {page} / {totalPages} - {total} resultats
      </span>
      <div>
        <Button variant="secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Precedent
        </Button>
        <Button variant="secondary" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          Suivant
        </Button>
      </div>
    </div>
  );
}
