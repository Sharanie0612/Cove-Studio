import assert from 'node:assert/strict';
import { InstrumentLive, stepDivision } from '../src/framework/surfaces/instrumentLive.ts';
import { engineering, divisions, cursorReadout } from '../src/framework/surfaces/instrumentView.ts';
import { mergeInstrumentData, readInstrumentFrame } from '../src/framework/surfaces/instrument/acquisition.ts';
import { initialSettings, synchronizeSettings } from '../src/framework/surfaces/instrument/settingsDraft.ts';
import { waveformGeometry } from '../src/framework/surfaces/instrument/waveformGeometry.ts';

const drain = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
const deferred = () => { let resolve, reject; const promise = new Promise((r, fail) => { resolve = r; reject = fail; }); return { promise, resolve, reject }; };
class Clock {
  time = 0; jobs = new Map(); id = 0;
  now = () => this.time;
  schedule = (callback, delay) => { const id = ++this.id; this.jobs.set(id, { callback, at: this.time + delay }); return id; };
  cancel = id => this.jobs.delete(id);
  async advance(milliseconds) {
    const until = this.time + milliseconds;
    while (true) {
      const next = [...this.jobs].sort((a, b) => a[1].at - b[1].at)[0];
      if (!next || next[1].at > until) break;
      this.time = next[1].at; this.jobs.delete(next[0]); next[1].callback(); await drain();
    }
    this.time = until; await drain();
  }
}

{
  const clock = new Clock(), frame = deferred(), command = deferred(), calls = [];
  let active = 0, maximum = 0;
  const loop = new InstrumentLive(async () => {
    active++; maximum = Math.max(active, maximum); calls.push('frame');
    if (calls.length === 1) await frame.promise;
    active--;
  }, () => false, clock);
  loop.start(200); await clock.advance(0);
  await clock.advance(1000);
  assert.deepEqual(calls, ['frame'], 'slow responses must never accumulate polling requests');
  const control = loop.execute(async () => { active++; maximum = Math.max(active, maximum); calls.push('control'); await command.promise; active--; });
  frame.resolve(); await drain();
  assert.deepEqual(calls, ['frame', 'control'], 'controls run after the current frame and before the next one');
  await clock.advance(1000); assert.equal(calls.length, 2);
  command.resolve(); await control; await clock.advance(50);
  assert.deepEqual(calls, ['frame', 'control', 'frame']); assert.equal(maximum, 1);
  loop.stop(); await clock.advance(10000); assert.equal(calls.length, 3);
}
{
  const clock = new Clock(), oldFrame = deferred(); let calls = 0, failures = 0;
  const loop = new InstrumentLive(async () => { calls++; if (calls === 1) await oldFrame.promise; }, () => { failures++; return false; }, clock);
  loop.start(200); await clock.advance(0); loop.stop(); loop.start(500);
  await clock.advance(1000); assert.equal(calls, 1, 'channel restart still waits for the old frame');
  oldFrame.resolve(); await drain(); await clock.advance(50); assert.equal(calls, 2);
  await clock.advance(500); assert.equal(calls, 3); assert.equal(failures, 0);
  loop.stop();
}
{
  const clock = new Clock(); let calls = 0;
  const loop = new InstrumentLive(async () => { calls++; throw new Error(calls === 1 ? 'busy' : 'disconnected'); }, error => error.message === 'busy', clock);
  loop.start(200); await clock.advance(1000);
  assert.equal(calls, 2, 'busy retries but a disconnect stops the loop');
  await assert.rejects(loop.execute(async () => { throw new Error('rejected control'); }));
  assert.equal(await loop.execute(async () => 42), 42, 'an unsuccessful command must not poison the queue');
}
assert.equal(stepDivision(.001, 1, 5e-10, 1000), .002);
assert.equal(stepDivision(.002, -1, 5e-10, 1000), .001);
assert.equal(stepDivision(.005, 1, 5e-10, 1000), .01);
assert.equal(stepDivision(.5, -1, .0002, 10000), .2);
assert.equal(stepDivision(1000, 1, 5e-10, 1000), 1000);
assert.equal(stepDivision(5e-10, -1, 5e-10, 1000), 5e-10);
console.log('Instrument live polling, control priority, stop/restart, failures and division checks passed.');
assert.equal(engineering(.0000012, 's'), '1.2 µs');
assert.equal(engineering(-.0005, 'V'), '-500 µV');
assert.equal(engineering(1e9, 'Sa/s'), '1 GSa/s');
assert.equal(engineering(null, 'V'), '—');
const steps = divisions(5e-10, 1000);
assert.equal(steps[0], 5e-10); assert.equal(steps.at(-1), 1000);
assert.equal(new Set(steps).size, steps.length);
assert.deepEqual(cursorReadout([0, .001, .002], [1, 5, 3], 0, 100), { ia: 0, ib: 2, ta: 0, tb: .002, va: 1, vb: 3, dt: .002, dv: 2, reciprocal: 500 });
assert.equal(cursorReadout([0], [1], 50, 50).reciprocal, null);
console.log('Engineering units, division slider bounds and local cursors passed.');

const wave = { channel: 1, time_s: [0, .001, .002], voltage_v: [-2, 0, 2], points: 3, timestamp: '2026-10-22T12:00:00Z', vpp_v: 4 };
const status = {
  identity: { model: 'Fixture', serial: '', firmware: '' }, address: 'fixture', trigger: 'RUN',
  timebase_s_div: .002, sample_rate_hz: 1000, timestamp: wave.timestamp,
  channels: [
    { channel: 1, enabled: true, scale_v_div: 1, offset_v: 1, coupling: 'DC' },
    { channel: 2, enabled: true, scale_v_div: .5, offset_v: -1, coupling: 'AC' },
  ],
  edge_trigger: { mode: 'EDGE', source: 'CHAN2', level_v: .2, slope: 'NEG', sweep: 'NORM' },
};
const measurements = { channel: 1, timestamp: wave.timestamp, items: [] };

{
  const clock = new Clock(), frame = deferred(), calls = [], accepted = [];
  const timing = { metadataAt: -Infinity, lastFrameAt: 0 };
  let frames = 0;
  const loop = new InstrumentLive(() => readInstrumentFrame({
    waveform: async () => { calls.push('waveform'); if (++frames === 1) await frame.promise; return wave; },
    status: async () => { calls.push('status'); return status; },
    measurements: async () => { calls.push('measurements'); return measurements; },
    accept: (kind) => accepted.push(kind),
    canReadMetadata: () => !loop.hasCommands(), timing, now: clock.now, onFrame: () => {},
  }), () => false, clock);
  loop.start(200); await clock.advance(0);
  const control = loop.execute(async () => { calls.push('control'); });
  frame.resolve(); await control; await drain();
  assert.deepEqual(calls, ['waveform', 'control'], 'a queued control skips optional metadata after the in-flight waveform');
  await clock.advance(200);
  assert.deepEqual(calls, ['waveform', 'control', 'waveform', 'status', 'measurements']);
  await clock.advance(200);
  assert.equal(calls.filter(value => value === 'status').length, 1, 'metadata reads retain their lower cadence');
  assert.deepEqual(accepted.slice(0, 4), ['waveform', 'waveform', 'status', 'measurements']);
  loop.stop();
}
{
  const pendingStatus = deferred(), calls = [];
  let visible = true;
  const read = readInstrumentFrame({
    waveform: async () => { calls.push('waveform'); return wave; },
    status: async () => { calls.push('status'); return pendingStatus.promise; },
    measurements: async () => { calls.push('measurements'); return measurements; },
    accept: () => {}, canReadMetadata: () => visible,
    timing: { metadataAt: -Infinity, lastFrameAt: 0 }, now: () => 3000, onFrame: () => {},
  });
  await drain(); visible = false; pendingStatus.resolve(status); await read;
  assert.deepEqual(calls, ['waveform', 'status'], 'hiding during a status read skips the remaining measurement request');
}
{
  const clock = new Clock(), oldFrame = deferred(); let calls = 0, failures = 0;
  const loop = new InstrumentLive(async () => { if (++calls === 1) await oldFrame.promise; }, () => { failures++; return false; }, clock);
  loop.start(200); await clock.advance(0); loop.stop(); loop.start(500);
  oldFrame.reject(new Error('old channel disconnected')); await drain(); await clock.advance(50);
  assert.equal(calls, 2); assert.equal(failures, 0, 'a failed previous channel must not stop the current generation');
  loop.stop();
}
{
  const previous = { waveform: wave, status };
  assert.equal(mergeInstrumentData(previous, 'waveform', { ...wave, timestamp: '2026-10-22T11:59:00Z' }), previous,
    'a delayed worker event must not replace a newer command result');
  const nextWave = { ...wave, timestamp: '2026-10-22T12:01:00Z' };
  assert.deepEqual(mergeInstrumentData(previous, 'waveform', nextWave), { status, waveform: nextWave });
  const draft = { ...initialSettings, scale: '0.123', level: '1.234', slope: 'RFAL', sweep: 'SING', triggerChannel: 4 };
  const channelDraft = synchronizeSettings(draft, status, 2, 'channel');
  assert.deepEqual(channelDraft, { ...draft, vscale: '0.5', offset: '-1', coupling: 'AC' },
    'switching channels preserves the unapplied horizontal and trigger drafts');
  assert.equal(draft.vscale, '1', 'readback must not mutate the retained draft');
  assert.deepEqual(synchronizeSettings(draft, status, 1, 'all'), {
    scale: '0.002', vscale: '1', offset: '1', coupling: 'DC', level: '0.2', slope: 'NEG', sweep: 'NORM', triggerChannel: 2,
  }, 'an explicit refresh applies actual settings for the selected channel');
  assert.equal(synchronizeSettings(draft, undefined, 2, 'channel'), draft);
  assert.equal(synchronizeSettings(draft, { ...status, edge_trigger: { mode: 'PULSE', sweep: 'AUTO' } }, 1, 'all').level, '1.234',
    'a non-edge trigger must not overwrite edge drafts');
}
{
  const geometry = waveformGeometry(wave, status.channels[0], 1, false);
  assert.equal(geometry.min, -5); assert.equal(geometry.max, 3);
  assert.equal(geometry.x(0), 52); assert.equal(geometry.x(2), 948);
  assert.equal(geometry.y(-5), 326); assert.equal(geometry.y(3), 38);
  const fitted = waveformGeometry(wave, status.channels[0], 1, true);
  assert.equal(fitted.min, -2); assert.equal(fitted.max, 2);
  assert.equal(waveformGeometry({ ...wave, voltage_v: [0, 0, 0] }, undefined, 1, true).path.includes('NaN'), false);
}
console.log('Instrument acquisition phases, visibility, stale data, settings drafts and plot geometry passed.');
