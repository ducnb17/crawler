import { onScopeDispose, ref, watch, type Ref } from "vue";
import type { RunEvent } from "@/types";

export interface UseSSEOptions {
  onEvent: (e: RunEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (e: Event) => void;
}

/**
 * Subscribe tới SSE endpoint, tự tái kết nối với backoff.
 */
export function useRunEvents(runId: Ref<string | null | undefined>, opts: UseSSEOptions) {
  const connected = ref(false);
  let es: EventSource | null = null;
  let stopped = false;
  let reconnectTimer: number | null = null;

  function stop() {
    stopped = true;
    if (es) {
      es.close();
      es = null;
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    connected.value = false;
  }

  function start(id: string) {
    stop();
    stopped = false;
    const url = `${(import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "")}/runs/${id}/events`;
    es = new EventSource(url, { withCredentials: true });
    connected.value = false;

    es.onopen = () => {
      connected.value = true;
      opts.onOpen?.();
    };
    es.onerror = (e) => {
      connected.value = false;
      opts.onError?.(e);
      es?.close();
      es = null;
      if (!stopped) {
        reconnectTimer = window.setTimeout(() => start(id), 2000);
      }
    };
    es.addEventListener("message", (ev) => handle(ev, "message"));
    // explicit named events
    for (const name of ["start", "page_done", "page_failed", "progress", "done", "error", "ping"]) {
      es.addEventListener(name, (ev) => handle(ev, name));
    }
  }

  function handle(ev: MessageEvent, fallback: string) {
    let payload: Record<string, unknown> = {};
    try {
      payload = JSON.parse(ev.data || "{}");
    } catch {
      payload = { event: fallback, data: ev.data };
    }
    const event = (payload.event as string) || fallback;
    opts.onEvent({ ...payload, event } as RunEvent);
  }

  // Auto start/stop when runId ref changes.
  const unwatch = watch(runId, (id) => {
    if (id) start(id);
    else stop();
  });

  function setRunId(id: string | null | undefined) {
    if (id) start(id);
    else stop();
  }

  onScopeDispose(() => {
    unwatch();
    stop();
  });

  return { connected, start, stop, setRunId };
}