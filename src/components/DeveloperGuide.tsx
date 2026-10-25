import { t } from '../core/i18n.ts';
import { useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Download,
  LoaderCircle,
  Sparkles,
} from 'lucide-react';
import { hostCall } from '../core/bridge';
import { useLocal } from '../core/storage';
import { traditional, vibe } from '../content/developerGuide';

export default function DeveloperGuide({
  native,
  toast,
}: {
  native: boolean;
  toast: (text: string) => void;
}) {
  const [track, setTrack] = useState<'traditional' | 'vibe'>('traditional');
  const [chapter, setChapter] = useState(0);
  const [completed, setCompleted] = useLocal<string[]>('guide-completed-v2', []);
  const [downloading, setDownloading] = useState(false);
  const [copied, setCopied] = useState('');
  const chapters = track === 'traditional' ? traditional() : vibe();
  const current = chapters[chapter];
  async function download() {
    setDownloading(true);
    try {
      const result = await hostCall<{ path: string } | null>('export_plugin_starter');
      if (result) toast(t('完整示例已保存'));
    } catch (failure) {
      toast((failure as Error).message);
    } finally {
      setDownloading(false);
    }
  }
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(text);
    } catch {
      toast(t('请手动选择文本复制'));
    }
  }
  function finish() {
    const key = `${track}:${chapter}`;
    if (!completed.includes(key)) setCompleted([...completed, key]);
    if (chapter < chapters.length - 1) setChapter(chapter + 1);
    else toast(t('教程已完成，现在可以交付你的插件了'));
  }
  return (
    <div className="page-body developer-page">
      <div className="page-heading">
        <div>
          <h1>{t('插件开发')}</h1>
          <p>{t('选一种适合你的方式，做出第一个可运行的插件。')}</p>
        </div>
        <button
          className="button primary"
          disabled={!native || downloading}
          onClick={() => void download()}
        >
          {downloading ? <LoaderCircle size={16} className="spin" /> : <Download size={16} />}
          {t('下载完整示例')}
        </button>
      </div>
      <div className="guide-tracks" aria-label={t('开发方式')}>
        <button
          className={track === 'traditional' ? 'active' : ''}
          aria-pressed={track === 'traditional'}
          onClick={() => {
            setTrack('traditional');
            setChapter(0);
          }}
        >
          <Code2 size={20} />
          <span>
            <b>{t('传统开发')}</b>
            <span>{t('自己编写 Python，一步步完成插件。')}</span>
          </span>
        </button>
        <button
          className={track === 'vibe' ? 'active' : ''}
          aria-pressed={track === 'vibe'}
          onClick={() => {
            setTrack('vibe');
            setChapter(0);
          }}
        >
          <Sparkles size={20} />
          <span>
            <b>Vibe Coding</b>
            <span>{t('用分阶段提示词，让 AI 帮你开发。')}</span>
          </span>
        </button>
      </div>
      <div className="guide-layout">
        <nav className="guide-chapters" aria-label={t('教程章节')}>
          {chapters.map((item, index) => (
            <button
              key={`${track}:${index}`}
              aria-current={chapter === index ? 'step' : undefined}
              className={chapter === index ? 'active' : ''}
              onClick={() => setChapter(index)}
            >
              <span className="chapter-number">
                {completed.includes(`${track}:${index}`) ? (
                  <Check size={13} />
                ) : (
                  String(index + 1).padStart(2, '0')
                )}
              </span>
              <span>{item.title}</span>
            </button>
          ))}
        </nav>
        <article className="guide-article" key={`${track}:${chapter}`}>
          <span className="eyebrow">
            {track === 'traditional' ? 'TRADITIONAL' : 'VIBE CODING'} /{' '}
            {String(chapter + 1).padStart(2, '0')}
          </span>
          <h2>{current.title}</h2>
          <p className="guide-subtitle">{current.subtitle}</p>
          <div className="guide-blocks">
            {current.blocks.map((block, index) =>
              block.kind === 'p' ? (
                <p key={index}>{block.text}</p>
              ) : (
                <div
                  className={`guide-code ${block.kind === 'prompt' ? 'prompt' : ''}`}
                  key={index}
                >
                  <div>
                    <span>
                      {block.kind === 'prompt' ? t('发送给 AI 的提示词') : t('示例与命令')}
                    </span>
                    <button className="quiet-button" onClick={() => void copy(block.text)}>
                      {copied === block.text ? <Check size={14} /> : <Copy size={14} />}{' '}
                      {copied === block.text ? t('已复制') : t('复制')}
                    </button>
                  </div>
                  <pre tabIndex={0}>{block.text}</pre>
                </div>
              ),
            )}
          </div>
          <footer className="guide-navigation">
            <button
              className="button"
              disabled={chapter === 0}
              onClick={() => setChapter(chapter - 1)}
            >
              <ArrowLeft size={15} />
              {t('上一节')}
            </button>
            <button className="button primary" onClick={finish}>
              {chapter === chapters.length - 1 ? <CheckCircle2 size={15} /> : null}
              {chapter === chapters.length - 1 ? t('完成教程') : t('完成并继续')}
              {chapter < chapters.length - 1 && <ArrowRight size={15} />}
            </button>
          </footer>
        </article>
      </div>
    </div>
  );
}
