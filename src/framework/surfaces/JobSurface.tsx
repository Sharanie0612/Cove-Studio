import { t, hostMessage } from '../../core/i18n.ts';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Copy, FileCheck2, LoaderCircle, Square } from 'lucide-react';
import { invoke, subscribe } from '../../core/bridge';
import type { PluginSurfaceProps } from '../contracts';
import './job.css';

export interface JobResult {
  state: 'idle' | 'running' | 'completed' | 'partial' | 'failed' | 'cancelled';
  message?: string;
  completed?: number;
  total?: number;
  output?: string;
  files?: { name: string; path: string; size: number }[];
  warnings?: string[];
  failures?: { id: string; error: string }[];
  instructions?: string[];
  instructionsTitle?: string;
  attribution?: string;
  revision?: number;
}

export default function JobSurface({ manifest, result, runtime, onConfigure }: PluginSurfaceProps) {
  const [job, setJob] = useState<JobResult>({ state: 'idle' });
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const revision = useRef(-1);
  const accept = useCallback((value: JobResult) => {
    if (
      !value ||
      !['idle', 'running', 'completed', 'partial', 'failed', 'cancelled'].includes(value.state)
    )
      return;
    if ((value.revision ?? 0) < revision.current) return;
    revision.current = value.revision ?? 0;
    setJob(value);
  }, []);
  useEffect(() => {
    if (result && typeof result === 'object' && 'state' in result) accept(result as JobResult);
  }, [result, accept]);
  useEffect(() => {
    let disposed = false;
    revision.current = -1;
    setJob({ state: 'idle' });
    setError('');
    if (runtime && !runtime.running) return;
    void invoke<JobResult>(manifest.id, manifest.ui.job!.snapshot)
      .then((value) => {
        if (!disposed) accept(value);
      })
      .catch((failure) => {
        if (!disposed) setError(String(failure.message));
      });
    const unsubscribe = subscribe((event) => {
      if (event.pluginId === manifest.id && event.event === 'job') {
        accept(event.data.result as JobResult);
        setError('');
      }
    });
    return () => {
      disposed = true;
      unsubscribe();
    };
  }, [manifest.id, manifest.ui.job?.snapshot, runtime?.pid, runtime?.running, accept]);
  useEffect(() => {
    if (job.state !== 'running') return;
    let disposed = false,
      pending = false;
    const timer = window.setInterval(async () => {
      if (pending) return;
      pending = true;
      try {
        const value = await invoke<JobResult>(manifest.id, manifest.ui.job!.snapshot);
        if (!disposed) {
          accept(value);
          setError('');
        }
      } catch (failure) {
        if (!disposed) setError(String((failure as Error).message));
      } finally {
        pending = false;
      }
    }, 1000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [job.state, manifest.id, manifest.ui.job?.snapshot, accept]);
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      setError(t('复制失败，请手动选择路径复制。'));
    }
  }
  async function cancel() {
    setCancelling(true);
    try {
      accept(await invoke<JobResult>(manifest.id, manifest.ui.job!.cancel));
    } catch (failure) {
      setError(String((failure as Error).message));
    } finally {
      setCancelling(false);
    }
  }
  const running = job.state === 'running';
  const knownTotal = typeof job.total === 'number' && job.total > 0;
  const labels = {
    idle: t('准备运行'),
    running: t('正在运行'),
    completed: t('运行完成'),
    partial: t('部分完成'),
    failed: t('运行失败'),
    cancelled: t('已停止'),
  };
  return (
    <div className="job-surface" aria-live="polite">
      <div className="job-heading">
        <span className="job-mark">
          {running ? <LoaderCircle size={28} className="spin" /> : <FileCheck2 size={28} />}
        </span>
        <div>
          <h2>{labels[job.state]}</h2>
          <p>{job.message || manifest.ui.empty?.description || manifest.description}</p>
        </div>
        {running && (
          <button className="button" disabled={cancelling} onClick={() => void cancel()}>
            <Square size={13} />
            {t('停止')}
          </button>
        )}
      </div>
      {running && (
        <div className="job-progress">
          <progress
            aria-label={t('任务进度')}
            max={knownTotal ? job.total : 1}
            value={knownTotal ? job.completed || 0 : undefined}
          />
          <span>{knownTotal ? `${job.completed || 0} / ${job.total}` : t('正在处理…')}</span>
        </div>
      )}
      {error && (
        <p className="error-note" role="alert">
          {hostMessage(error)}
        </p>
      )}
      {job.output && (
        <div className="job-directory">
          <span>{t('输出目录')}</span>
          <code>{job.output}</code>
          <button
            className="icon-button"
            aria-label={t('复制输出目录')}
            onClick={() => void copy(job.output!)}
          >
            <Copy size={14} />
          </button>
        </div>
      )}
      {!!job.files?.length && (
        <div className="job-files">
          {job.files.map((file) => (
            <article key={file.path}>
              <FileCheck2 size={19} />
              <div>
                <b>{file.name}</b>
                <p>{file.path}</p>
              </div>
              <small>{(file.size / 1024).toFixed(1)} KB</small>
              <button
                className="icon-button"
                aria-label={t('复制路径 {p0}', { p0: file.name })}
                onClick={() => void copy(file.path)}
              >
                <Copy size={14} />
              </button>
            </article>
          ))}
        </div>
      )}
      {!!job.failures?.length && (
        <div className="job-notes" role="alert">
          {job.failures.map((item) => (
            <p key={item.id}>
              <b>{item.id}</b> · {item.error}
            </p>
          ))}
        </div>
      )}
      {!!job.warnings?.length && (
        <div className="job-notes">
          {job.warnings.map((warning, i) => (
            <p key={i}>{warning}</p>
          ))}
        </div>
      )}
      {!!job.instructions?.length && (
        <section className="job-instructions">
          <h3>{job.instructionsTitle || t('后续步骤')}</h3>
          <ol>
            {job.instructions.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </section>
      )}
      {!running && (
        <button className="button primary" onClick={onConfigure}>
          {job.state === 'idle' ? manifest.ui.actions[0].label : t('再次运行')}
        </button>
      )}
      {job.attribution && (
        <details className="job-attribution">
          <summary>{t('来源与许可')}</summary>
          <p>{job.attribution}</p>
        </details>
      )}
    </div>
  );
}
