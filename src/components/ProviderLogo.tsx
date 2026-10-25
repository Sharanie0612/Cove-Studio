import { t } from '../core/i18n.ts';
import codex from '../../assets/providers/codex.svg';
import claude from '../../assets/providers/claude-code.png';
import cursor from '../../assets/providers/cursor.svg';
import deepseek from '../../assets/providers/deepseek-harness.svg';
import zcode from '../../assets/providers/zcode.png';
import workbuddy from '../../assets/providers/workbuddy.svg';
import trae from '../../assets/providers/trae.png';

const marks: Record<string, string> = {
  codex,
  'claude-code': claude,
  cursor,
  'deepseek-harness': deepseek,
  zcode,
  workbuddy,
  trae,
};
export default function ProviderLogo({ id, name }: { id: string; name: string }) {
  return (
    <span className={`provider-logo provider-${id}`}>
      <img src={marks[id]} alt={t('{p0} 标识', { p0: name })} draggable={false} />
    </span>
  );
}
