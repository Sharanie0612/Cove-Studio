import assert from 'node:assert/strict';
import { AssistantStateStore } from '../src/core/assistantStateStore.ts';
import { isExternalProfile, profileSourceLabel } from '../src/framework/profiles.ts';

const settle = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const state = (selected = [], pending = []) => ({ tools: [], selected, pending, audit: [], enabled: true });
class Clock {
  time = 0; jobs = new Map(); id = 0;
  schedule = (callback, delay) => { const id = ++this.id; this.jobs.set(id, { callback, at: this.time + delay }); return id; };
  cancel = id => this.jobs.delete(id);
  async advance(milliseconds) {
    const until = this.time + milliseconds;
    while (true) {
      const next = [...this.jobs].sort((a, b) => a[1].at - b[1].at)[0];
      if (!next || next[1].at > until) break;
      this.time = next[1].at; this.jobs.delete(next[0]); next[1].callback(); await settle();
    }
    this.time = until; await settle();
  }
}

{
  const clock = new Clock(), slow = deferred();
  let calls = 0, active = 0, maximum = 0;
  const store = new AssistantStateStore(async () => {
    calls++; active++; maximum = Math.max(maximum, active);
    if (calls === 1) await slow.promise;
    active--;
    return state(['tool.a']);
  }, clock);
  const stopHidden = store.subscribe(() => {}, false);
  await clock.advance(2000);
  assert.equal(calls, 0, 'mounted inactive pages do not start polling');
  const stopAi = store.subscribe(() => {}), stopMcp = store.subscribe(() => {}), stopApprovals = store.subscribe(() => {});
  await clock.advance(5000);
  assert.equal(calls, 1, 'three consumers share one slow request without a polling backlog');
  slow.resolve(); await settle();
  assert.equal(store.getSnapshot().loaded, true);
  assert.equal(clock.jobs.size, 1, 'one timer serves all consumers');
  await clock.advance(700);
  assert.equal(calls, 2);
  stopAi(); stopMcp();
  await clock.advance(700);
  assert.equal(calls, 3, 'approvals stay live while both management pages are inactive');
  stopApprovals();
  store.invalidate();
  await clock.advance(5000);
  assert.equal(calls, 3, 'inactive subscribers and host events cannot keep polling alive');
  assert.equal(maximum, 1);
  stopHidden();
}

{
  const clock = new Clock(), beforeSave = deferred(), afterSave = deferred(), observed = [];
  let calls = 0;
  const store = new AssistantStateStore(() => ++calls === 1 ? beforeSave.promise : afterSave.promise, clock);
  const stop = store.subscribe(() => observed.push(store.getSnapshot().state.selected));
  const saved = store.refresh(), secondConsumer = store.refresh();
  beforeSave.resolve(state(['old-grant'])); await settle();
  assert.equal(calls, 2, 'mutation refreshes coalesce into one fresh read after the old request');
  assert.deepEqual(observed, [], 'a pre-mutation grant snapshot must never overwrite saved state');
  afterSave.resolve(state(['new-grant']));
  assert.deepEqual((await saved).selected, ['new-grant']);
  assert.deepEqual((await secondConsumer).selected, ['new-grant']);
  assert.deepEqual(observed, [['new-grant']]);
  stop();
}

{
  const clock = new Clock(), old = deferred();
  let calls = 0;
  const store = new AssistantStateStore(() => ++calls === 1 ? old.promise : Promise.resolve(state(['resumed'])), clock);
  const stop = store.subscribe(() => {});
  store.setVisible(false);
  old.resolve(state(['stale'])); await settle();
  assert.equal(store.getSnapshot().loaded, false, 'hidden lifecycle drops an unfinished snapshot');
  await clock.advance(5000);
  assert.equal(calls, 1);
  store.setVisible(true); await settle();
  assert.deepEqual(store.getSnapshot().state.selected, ['resumed']);
  assert.equal(calls, 2, 'returning to the application immediately reconciles state');
  stop();
}

{
  const clock = new Clock(), old = deferred();
  let calls = 0;
  const store = new AssistantStateStore(() => ++calls === 1 ? old.promise : Promise.resolve(state(['new-session'])), clock);
  const stop = store.subscribe(() => {});
  stop();
  const stopAgain = store.subscribe(() => {});
  old.reject(new Error('obsolete runtime failure')); await settle();
  assert.equal(calls, 2);
  assert.equal(store.getSnapshot().error, '', 'a late failure from a detached consumer cannot poison the resumed view');
  assert.deepEqual(store.getSnapshot().state.selected, ['new-session']);
  stopAgain();
}

{
  const clock = new Clock(), pending = [{ id: 'approval-1', arguments: { command: 'write' } }];
  let calls = 0;
  const store = new AssistantStateStore(async () => {
    calls++;
    if (calls === 2) throw new Error('host temporarily unavailable');
    return state([], calls === 1 ? pending : []);
  }, clock);
  const stop = store.subscribe(() => {}); await settle();
  store.dismissApproval('approval-1');
  assert.deepEqual(store.getSnapshot().state.pending, [], 'an acknowledged approval closes immediately');
  await settle();
  assert.match(store.getSnapshot().error, /temporarily unavailable/);
  assert.deepEqual(store.getSnapshot().state.pending, [], 'a failed refresh must not redisplay an already decided write');
  await clock.advance(700);
  assert.equal(store.getSnapshot().error, '', 'a later successful snapshot clears the transient error');
  stop();
}

{
  const clock = new Clock(), pending = deferred();
  const store = new AssistantStateStore(() => pending.promise, clock);
  const stop = store.subscribe(() => {});
  const unchanged = store.getSnapshot();
  stop(); pending.resolve(state(['detached'])); await settle();
  assert.equal(store.getSnapshot(), unchanged, 'unmount does not publish a late snapshot');
  assert.equal(clock.jobs.size, 0);
}

assert.equal(isExternalProfile({ source: 'external-fixture' }), true);
assert.equal(profileSourceLabel({ source: 'external-fixture' }), '外部配置');
assert.equal(profileSourceLabel({ source: 'vendor', sourceLabel: 'Device profiles' }), 'Device profiles');
assert.equal(isExternalProfile({ source: 'workbench' }), false);
console.log('Shared assistant snapshots, mutation freshness, lifecycle, approval recovery and profile adapters passed.');

