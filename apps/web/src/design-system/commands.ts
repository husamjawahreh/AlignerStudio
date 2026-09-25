/** Keyboard / command interaction foundation registration. */

export type CommandId = string;

export interface CommandDefinition {
  id: CommandId;
  label: string;
  shortcut?: string;
  enabled?: boolean;
  run: () => void;
}

export function matchCommandShortcut(
  event: Pick<KeyboardEvent, "key" | "metaKey" | "ctrlKey" | "altKey" | "shiftKey">,
  commands: readonly CommandDefinition[],
): CommandDefinition | null {
  const combo = [
    event.metaKey || event.ctrlKey ? "mod" : null,
    event.altKey ? "alt" : null,
    event.shiftKey ? "shift" : null,
    event.key.length === 1 ? event.key.toLowerCase() : event.key,
  ]
    .filter(Boolean)
    .join("+");
  return (
    commands.find(
      (command) => command.enabled !== false && command.shortcut?.toLowerCase() === combo,
    ) ?? null
  );
}
