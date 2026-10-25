/** A response-paced polling loop sharing one queue with foreground controls. */
export interface LiveClock {
  now(): number;
  schedule(callback: () => void, delay: number): unknown;
  cancel(handle: unknown): void;
}
const browserClock: LiveClock = {
  now: () => performance.now(),
  schedule: (callback, delay) => setTimeout(callback, delay),
  cancel: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

export class InstrumentLive {
  private tail: Promise<void> = Promise.resolve();
  private work = 0;
  private commands = 0;
  private generation = 0;
  private timer: unknown;
  private running = false;
  private read: () => Promise<void>;
  private failure: (error: unknown) => boolean;
  private clock: LiveClock;
  constructor(
    read: () => Promise<void>,
    failure: (error: unknown) => boolean,
    clock: LiveClock = browserClock,
  ) {
    this.read = read;
    this.failure = failure;
    this.clock = clock;
  }

  hasCommands() {
    return this.commands > 0;
  }

  private enqueue<T>(task: () => Promise<T>): Promise<T> {
    this.work++;
    const result = this.tail.then(task);
    this.tail = result
      .then(
        () => {},
        () => {},
      )
      .finally(() => {
        this.work--;
      });
    return result;
  }

  execute<T>(task: () => Promise<T>): Promise<T> {
    this.commands++;
    return this.enqueue(task).finally(() => {
      this.commands--;
    });
  }

  start(interval: number) {
    this.stop();
    this.running = true;
    const generation = this.generation;
    const current = () => this.running && generation === this.generation;
    const schedule = (delay: number) => {
      if (current())
        this.timer = this.clock.schedule(() => {
          void tick();
        }, delay);
    };
    const tick = async () => {
      if (!current()) return;
      if (this.work > 0) {
        schedule(50);
        return;
      }
      const started = this.clock.now();
      try {
        await this.enqueue(this.read);
      } catch (error) {
        // An old channel/visibility generation must not stop a newer loop.
        if (!current()) return;
        if (!this.failure(error)) {
          this.stop();
          return;
        }
      }
      schedule(Math.max(50, interval - (this.clock.now() - started)));
    };
    schedule(0);
  }

  stop() {
    this.running = false;
    this.generation++;
    if (this.timer !== undefined) this.clock.cancel(this.timer);
    this.timer = undefined;
  }
}

/** Move to an adjacent 1-2-5 instrument division without floating point drift. */
export function stepDivision(value: number, direction: -1 | 1, minimum: number, maximum: number) {
  if (!Number.isFinite(value) || value <= 0) return minimum;
  const candidates: number[] = [];
  const exponent = Math.floor(Math.log10(value));
  for (let power = exponent - 2; power <= exponent + 2; power++)
    for (const factor of [1, 2, 5]) candidates.push(Number((factor * 10 ** power).toPrecision(12)));
  const next =
    direction === 1
      ? candidates.find((v) => v > value * (1 + 1e-9))
      : candidates.filter((v) => v < value * (1 - 1e-9)).at(-1);
  return Math.max(minimum, Math.min(maximum, next ?? value));
}
