"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiList } from "@/src/lib/api";

type QueryValue = string | number | boolean | null | undefined;
type QueryParams = Record<string, QueryValue>;

function normalizeQuery(query: QueryParams) {
  return Object.fromEntries(
    Object.entries(query)
      .filter(([, value]) => value !== undefined && value !== null && value !== "")
      .sort(([left], [right]) => left.localeCompare(right))
  ) as Record<string, string | number | boolean>;
}

export function usePagedApi<T>(path: string, extraQuery: QueryParams = {}, pageSize = 10) {
  const [page, setPage] = useState(1);
  const queryParams = useMemo(
    () => normalizeQuery({ ...extraQuery, page, page_size: pageSize }),
    [extraQuery, page, pageSize]
  );
  const query = useQuery({
    queryKey: [path, queryParams],
    queryFn: () => apiList<T>(path, { query: queryParams })
  });
  return { ...query, page, pageSize, setPage, queryParams };
}
