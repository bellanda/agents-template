/**
 * One onboarding balloon on screen at a time. On /chat the Escalação strip and the client panel
 * would open two popovers together and overlap (and a balloon over a toolbar eats the clicks).
 * The first eligible balloon takes the slot; the others queue and open in turn when it is
 * dismissed or unmounted. Module state on purpose: balloons live in unrelated subtrees.
 */
let activeMark: string | null = null;
const waitingMarks: string[] = [];
const listeners = new Set<() => void>();

function notifyBalloonSlotListeners(): void {
  for (const listener of listeners) listener();
}

/** Asks to show `mark`: opens now if nobody holds the slot, else waits its turn. Idempotent. */
export function requestBalloonSlot(mark: string): void {
  if (activeMark === mark || waitingMarks.includes(mark)) return;
  if (activeMark !== null) {
    waitingMarks.push(mark);
    return;
  }
  activeMark = mark;
  notifyBalloonSlotListeners();
}

/** Gives the slot (or the place in line) back; the next waiting balloon opens. */
export function releaseBalloonSlot(mark: string): void {
  const position = waitingMarks.indexOf(mark);
  if (position !== -1) waitingMarks.splice(position, 1);
  if (activeMark !== mark) return;
  activeMark = waitingMarks.shift() ?? null;
  notifyBalloonSlotListeners();
}

export function getActiveBalloonMark(): string | null {
  return activeMark;
}

export function subscribeBalloonSlot(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
