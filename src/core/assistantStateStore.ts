import type { AssistantState } from './types';

export interface AssistantSnapshot {
  state: AssistantState;
  error: string;
  loaded: boolean;
}

interface Clock {
  schedule(callback: () => void, delay: number): unknown;
  cancel(handle: unknown): void;
}

const clock: Clock = {
  schedule: (callback, delay) => setTimeout(callback, delay),
  cancel: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

/** One host snapshot stream shared by pages and the global approval dialog. */
export class AssistantStateStore {
  private snapshot: AssistantSnapshot = {
    state: { tools: [], selected: [], pending: [], audit: [], enabled: true },
    error: '',
    loaded: false,
  };
  private listeners = new Map<() => void, boolean>();
  private visible = true;
  private revision = 0;
  private requested = false;
  private inFlight: Promise<AssistantState> | undefined;
  private timer: unknown;
  private load: () => Promise<AssistantState>;
  private clock: Clock;

  constructor(load: () => Promise<AssistantState>, scheduler: Clock = clock) {
    this.load = load;
    this.clock = scheduler;
  }

  getSnapshot = () => this.snapshot;

  private polling() {
    return this.visible && [...this.listeners.values()].some(Boolean);
  }

  subscribe(listener: () => void, active = true) {
    const wasPolling = this.polling();
    this.listeners.set(listener, active);
    this.reconcile(wasPolling);
    return () => {
      const wasPolling = this.polling();
      this.listeners.delete(listener);
      this.reconcile(wasPolling);
    };
  }

  setVisible(visible: boolean) {
    const wasPolling = this.polling();
    this.visible = visible;
    this.reconcile(wasPolling);
  }

  invalidate() {
    if (this.polling()) void this.refresh().catch(() => undefined);
  }

  /** Remove an acknowledged decision immediately, even if the next read fails. */
  dismissApproval = (id: string) => {
    this.revision++;
    this.requested = true;
    this.publish({
      ...this.snapshot,
      state: {
        ...this.snapshot.state,
        pending: this.snapshot.state.pending.filter((item) => item.id !== id),
      },
    });
    void this.read().catch(() => undefined);
  };

  private reconcile(wasPolling: boolean) {
    if (wasPolling === this.polling()) return;
    if (this.polling()) void this.refresh().catch(() => undefined);
    else {
      this.clearTimer();
      this.revision++;
      this.requested = false;
    }
  }

  private clearTimer() {
    if (this.timer !== undefined) this.clock.cancel(this.timer);
    this.timer = undefined;
  }

  private publish(snapshot: AssistantSnapshot) {
    this.snapshot = snapshot;
    this.listeners.forEach((_, listener) => listener());
  }

  /** A mutation refresh must not resolve with a snapshot read before that mutation. */
  refresh = (): Promise<AssistantState> => {
    this.revision++;
    this.requested = true;
    return this.read();
  };

  private read(): Promise<AssistantState> {
    this.clearTimer();
    if (!this.inFlight) {
      this.inFlight = this.drain().finally(() => {
        this.inFlight = undefined;
        if (this.polling()) {
          this.timer = this.clock.schedule(() => {
            this.timer = undefined;
            void this.refresh().catch(() => undefined);
          }, 700);
        }
      });
    }
    return this.inFlight.then(() => (this.requested ? this.read() : this.snapshot.state));
  }

  private async drain(): Promise<AssistantState> {
    while (this.requested) {
      this.requested = false;
      const revision = this.revision;
      try {
        const state = await this.load();
        if (revision === this.revision) this.publish({ state, error: '', loaded: true });
      } catch (failure) {
        if (revision !== this.revision) continue;
        this.publish({ ...this.snapshot, error: String((failure as Error).message || failure) });
        throw failure;
      }
    }
    return this.snapshot.state;
  }
}
