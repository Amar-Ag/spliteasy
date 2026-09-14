import { useCallback, useEffect, useState, type DependencyList } from 'react';
import { errorMessage } from '../apiError';

interface ResourceState<T> {
  data?: T;
  error?: string;
  loading: boolean;
}

/** Loads async data when `deps` change. `reload()` refetches while keeping the current data on screen. */
export function useResource<T>(load: () => Promise<T>, deps: DependencyList) {
  const [state, setState] = useState<ResourceState<T>>({ loading: true });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true }));
    load().then(
      (data) => !cancelled && setState({ data, loading: false }),
      (err) => !cancelled && setState((s) => ({ data: s.data, error: errorMessage(err), loading: false })),
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, reload };
}
