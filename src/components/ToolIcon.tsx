import type { Manifest } from '../core/types';
import PluginGlyph from '../framework/PluginGlyph';

export function memoryLabel(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
export function ToolIcon({ tool }: { tool: Manifest }) {
  return (
    <span className="tool-icon cove-plugin-icon" aria-hidden="true">
      <PluginGlyph tool={tool} />
    </span>
  );
}
