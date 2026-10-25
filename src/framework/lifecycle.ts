import { t, getLocale } from '../core/i18n.ts';
import type { WorkProtection } from '../core/types';

export function protectionDescription(work: WorkProtection): string {
  const parts = [
    work.connections && t('{p0} 个连接', { p0: work.connections }),
    work.backgroundTasks && t('{p0} 个后台任务', { p0: work.backgroundTasks }),
    work.commands && t('{p0} 个正在执行或等待确认的命令', { p0: work.commands }),
  ].filter(Boolean);
  return t(
    '当前有 {p0}。继续会结束这些工作并释放进程，未完成的结果可能丢失。配置和已保存数据保留。',
    { p0: parts.join(getLocale() === 'en-US' ? ', ' : '、') || t('活动工作') },
  );
}
