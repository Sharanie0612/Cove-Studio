import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, FolderOpen, LoaderCircle, Minus, X } from 'lucide-react';
import { languages, setLocale, t, type Locale } from '../core/i18n';
import { useLocale } from '../core/useLocale';
import mark from '../../assets/cove-mark.svg';

type Page = 'language' | 'location' | 'license' | 'installing' | 'finish';
interface SetupState {
  version: string;
  directory: string;
  locale: Locale;
  license: string;
  previewPage?: Page;
}
interface Progress {
  phase: string;
  percent?: number | null;
  completedFiles?: number;
  totalFiles?: number;
}
type Outcome = { ok: boolean; code?: string };
interface SetupApi {
  state(): Promise<SetupState>;
  set_locale(locale: string): Promise<Outcome>;
  browse(): Promise<string | null>;
  install(directory: string, accepted: boolean, closeExisting: boolean): Promise<Outcome>;
  progress(): Promise<Progress>;
  finish(launch: boolean, desktop: boolean): Promise<Outcome>;
  window_action(action: string): Promise<Outcome>;
}
function api(): SetupApi | undefined {
  return window.pywebview?.api as unknown as SetupApi | undefined;
}
function errorText(code: string) {
  switch (code) {
    case 'INVALID_DIRECTORY':
      return t('无法使用这个安装位置，请选择其他文件夹。');
    case 'FILES_BUSY':
      return t('安装文件正在使用中，请稍后重试。');
    case 'SETUP_BUSY':
      return t('另一个安装器正在运行，请完成后重试。');
    case 'LOAD_FAILED':
      return t('无法读取安装文件，请重新下载安装包。');
    case 'LAUNCH_FAILED':
      return t('无法启动 Cove，请使用安装位置中的 Cove.exe 重试。');
    case 'SHORTCUT_FAILED':
      return t('无法创建桌面快捷方式。可取消该选项后继续。');
    default:
      return t('安装未完成。请检查安装位置并重试。');
  }
}
function progressText(phase: string) {
  switch (phase) {
    case 'closing':
      return t('正在等待旧窗口退出');
    case 'checking':
      return t('正在检查安装环境');
    case 'copying':
      return t('正在复制运行文件');
    case 'verifying':
      return t('正在校验安装文件');
    case 'finishing':
      return t('正在完成安装');
    default:
      return t('正在准备安装文件');
  }
}
export default function SetupApp() {
  const locale = useLocale();
  const [state, setState] = useState<SetupState>();
  const [directory, setDirectory] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [launch, setLaunch] = useState(true);
  const [desktop, setDesktop] = useState(true);
  const [page, setPage] = useState<Page>('language');
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(false);
  const [progress, setProgress] = useState<Progress>({ phase: 'preparing' });
  const cancelRef = useRef<HTMLButtonElement>(null);
  const primaryRef = useRef<HTMLButtonElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const steps = [t('语言'), t('安装位置'), t('开源许可'), t('安装进度'), t('安装完成')];
  const pages: Page[] = ['language', 'location', 'license', 'installing', 'finish'];
  const index = pages.indexOf(page);
  useEffect(() => {
    let loaded = false;
    const load = async () => {
      if (loaded || !api()) return;
      loaded = true;
      try {
        const value = await api()!.state();
        setLocale(value.locale);
        setState(value);
        setDirectory(value.directory);
        if (value.previewPage && pages.includes(value.previewPage)) setPage(value.previewPage);
      } catch {
        setError('LOAD_FAILED');
      }
    };
    void load();
    window.addEventListener('pywebviewready', load);
    return () => window.removeEventListener('pywebviewready', load);
  }, []);
  useEffect(() => {
    headingRef.current?.focus();
  }, [page]);
  useEffect(() => {
    if (closing) cancelRef.current?.focus();
  }, [closing]);
  useEffect(() => {
    if (page !== 'installing') return;
    let alive = true;
    const update = async () => {
      try {
        const next = await api()?.progress();
        if (alive && next) setProgress(next);
      } catch {}
    };
    void update();
    const timer = setInterval(update, 300);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [page]);
  const dismiss = () => {
    setClosing(false);
    primaryRef.current?.focus();
  };
  async function install(closeExisting = false) {
    if (!api() || busy || !accepted) return;
    setBusy(true);
    setError('');
    setClosing(false);
    setProgress({ phase: closeExisting ? 'closing' : 'preparing' });
    setPage('installing');
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    try {
      const reply = await api()!.install(directory, accepted, closeExisting);
      if (reply.ok) {
        setProgress({ phase: 'finished', percent: 100 });
        setPage('finish');
      } else {
        setPage('license');
        if (reply.code === 'DESKTOP_RUNNING') setClosing(true);
        else setError(reply.code || 'INSTALL_FAILED');
      }
    } catch {
      setPage('license');
      setError('INSTALL_FAILED');
    } finally {
      setBusy(false);
    }
  }
  async function next() {
    setError('');
    if (page === 'language') {
      setPage('location');
      return;
    }
    if (page === 'location') {
      if (!/^(?:[a-z]:[\\/]|\\\\)/i.test(directory) || /["\n\r<>|]/.test(directory)) {
        setError('INVALID_DIRECTORY');
        return;
      }
      setPage('license');
      return;
    }
    if (page === 'license') {
      await install();
      return;
    }
    if (page === 'finish') {
      setStarting(true);
      try {
        const reply = await api()!.finish(launch, desktop);
        if (!reply.ok)
          setError(reply.code === 'SHORTCUT_FAILED' ? 'SHORTCUT_FAILED' : 'LAUNCH_FAILED');
      } catch {
        setError('LAUNCH_FAILED');
      } finally {
        setStarting(false);
      }
    }
  }
  return (
    <div className={`app-shell setup-shell ${state ? 'setup-ready' : ''}`} data-page={page}>
      <header
        className="window-titlebar setup-titlebar"
        onPointerDown={(event) => {
          if (
            event.button === 0 &&
            document.documentElement.dataset.windowDrag !== 'native' &&
            !(event.target as Element).closest('button,select,input')
          ) {
            event.preventDefault();
            void api()?.window_action('drag');
          }
        }}
      >
        <div className="wordmark">
          <img src={mark} alt="" />
          <b>Cove Studio</b>
        </div>
        <div className="window-drag" />
        <div className="window-controls">
          <button aria-label={t('最小化')} onClick={() => void api()?.window_action('minimize')}>
            <Minus size={14} />
          </button>
          <button
            className="window-close"
            disabled={busy}
            aria-label={t('关闭安装器')}
            onClick={() => void api()?.window_action('close')}
          >
            <X size={14} />
          </button>
        </div>
      </header>
      <main className="setup-content">
        <div className="setup-heading">
          <span data-version={state?.version}>Cove Studio {state?.version}</span>
          <span>{t('第 {p0} 步，共 {p1} 步', { p0: index + 1, p1: steps.length })}</span>
        </div>
        <ol className="setup-steps" aria-label={t('安装步骤')}>
          {steps.map((label, i) => (
            <li
              key={pages[i]}
              aria-current={i === index ? 'step' : undefined}
              className={i < index ? 'completed' : ''}
            >
              <span>{i < index ? <Check size={12} /> : i + 1}</span>
              {label}
            </li>
          ))}
        </ol>
        <h1 ref={headingRef} tabIndex={-1} className="setup-page-title">
          {page === 'language'
            ? t('选择安装语言')
            : page === 'location'
              ? t('选择安装位置')
              : page === 'license'
                ? t('阅读开源许可')
                : page === 'installing'
                  ? t('正在安装')
                  : t('安装完成')}
        </h1>
        {page === 'language' && (
          <>
            <p className="setup-lead">{t('请选择本次安装使用的语言。')}</p>
            <section className="setup-card setup-language">
              <label htmlFor="setup-language">{t('界面语言')}</label>
              <select
                id="setup-language"
                value={locale}
                disabled={!state}
                onChange={async (event) => {
                  const value = event.target.value as Locale;
                  setLocale(value);
                  try {
                    await api()?.set_locale(value);
                  } catch {
                    setError('LOAD_FAILED');
                  }
                }}
              >
                {languages.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </section>
          </>
        )}
        {page === 'location' && (
          <>
            <p className="setup-lead">{t('选择 Cove Studio 的安装文件夹。')}</p>
            <section className="setup-card">
              <label htmlFor="setup-directory">{t('安装位置')}</label>
              <div className="setup-location">
                <input
                  id="setup-directory"
                  value={directory}
                  onChange={(event) => setDirectory(event.target.value)}
                  spellCheck={false}
                />
                <button
                  className="button"
                  aria-label={t('选择安装位置')}
                  onClick={async () => {
                    const folder = await api()?.browse();
                    if (folder) setDirectory(folder);
                  }}
                >
                  <FolderOpen size={16} />
                </button>
              </div>
              <p>{t('已有设置、插件和连接配置会保留。')}</p>
            </section>
          </>
        )}
        {page === 'license' && (
          <>
            <p className="setup-lead">{t('继续安装前，请阅读并接受以下开源许可。')}</p>
            <pre className="setup-license-text" tabIndex={0} aria-label={t('开源许可')}>
              {state?.license}
            </pre>
            <label className="setup-check">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              {t('我已阅读并同意开源许可。')}
            </label>
          </>
        )}
        {page === 'installing' && (
          <div className="setup-installation" role="status">
            <LoaderCircle className="spin" size={25} />
            <b>{progressText(progress.phase)}</b>
            <div
              className={`setup-progress-track ${progress.percent == null ? 'indeterminate' : ''}`}
              role="progressbar"
              aria-label={t('安装进度')}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress.percent ?? undefined}
            >
              <span style={{ width: progress.percent == null ? '28%' : `${progress.percent}%` }} />
            </div>
            <div className="setup-progress-detail">
              <span>
                {progress.totalFiles
                  ? t('已复制 {p0} / {p1} 个文件', {
                      p0: progress.completedFiles || 0,
                      p1: progress.totalFiles,
                    })
                  : t('请保持安装器打开')}
              </span>
              <span>{progress.percent != null ? `${progress.percent}%` : t('处理中…')}</span>
            </div>
          </div>
        )}
        {page === 'finish' && (
          <div className="setup-complete">
            <span className="setup-checkmark">
              <Check size={24} />
            </span>
            <p>{t('Cove Studio {p0} 已安装。', { p0: state?.version || '' })}</p>
            <code className="setup-installed-path">{directory}</code>
            <label className="setup-check">
              <input
                type="checkbox"
                disabled={starting}
                checked={launch}
                onChange={(event) => setLaunch(event.target.checked)}
              />
              {t('打开 Cove Studio')}
            </label>
            <label className="setup-check">
              <input
                type="checkbox"
                disabled={starting}
                checked={desktop}
                onChange={(event) => setDesktop(event.target.checked)}
              />
              {t('创建桌面快捷方式')}
            </label>
          </div>
        )}
        {error && (
          <p className="setup-error" role="alert">
            {errorText(error)}
          </p>
        )}
      </main>
      <footer className="setup-footer">
        <span>{busy ? t('请保持安装器打开') : t('仅为当前用户安装')}</span>
        <div>
          {index > 0 && index < 3 && (
            <button
              className="button"
              onClick={() => {
                setError('');
                setPage(pages[index - 1]);
              }}
            >
              <ArrowLeft size={14} />
              {t('上一步')}
            </button>
          )}
          {page !== 'finish' && (
            <button
              className="button"
              disabled={busy}
              onClick={() => void api()?.window_action('close')}
            >
              {t('取消')}
            </button>
          )}
          <button
            ref={primaryRef}
            className="button primary"
            disabled={
              busy ||
              starting ||
              !state ||
              page === 'installing' ||
              (page === 'license' && !accepted) ||
              (page === 'location' && !directory.trim())
            }
            onClick={() => void next()}
          >
            {page === 'finish'
              ? t('完成')
              : page === 'license'
                ? t('安装')
                : page === 'installing'
                  ? t('正在安装')
                  : t('下一步')}
            {!busy && page !== 'finish' && <ArrowRight size={14} />}
          </button>
        </div>
      </footer>
      {closing && (
        <div className="setup-modal-backdrop">
          <section
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="close-cove-title"
            className="setup-modal"
            onKeyDown={(event) => {
              if (event.key === 'Escape') dismiss();
              if (event.key === 'Tab') {
                const buttons = event.currentTarget.querySelectorAll('button');
                if (event.shiftKey && document.activeElement === buttons[0]) {
                  event.preventDefault();
                  buttons[1].focus();
                } else if (!event.shiftKey && document.activeElement === buttons[1]) {
                  event.preventDefault();
                  buttons[0].focus();
                }
              }
            }}
          >
            <h2 id="close-cove-title">{t('先退出正在运行的 Cove')}</h2>
            <p>
              {t(
                '安装器将请求旧窗口正常退出。若有未完成工作，请先在 Cove 中处理；取消退出会暂停本次安装。',
              )}
            </p>
            <div>
              <button ref={cancelRef} className="button" onClick={dismiss}>
                {t('取消')}
              </button>
              <button className="button primary" onClick={() => void install(true)}>
                {t('退出并继续')}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
