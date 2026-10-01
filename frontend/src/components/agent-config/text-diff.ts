/**
 * Line-level text diff for the version preview ("what changes if I restore this version?").
 *
 * Hand-rolled on purpose: the instructions are capped at ~20k chars (hundreds of lines), so a
 * plain LCS table is instant and a diff dependency (new package) is not justified.
 */

export type DiffLineKind = "same" | "added" | "removed";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
}

/** Placeholder for a run of unchanged lines hidden by `collapseUnchanged`. */
export interface DiffGap {
  kind: "gap";
  hiddenLines: number;
}

export type DiffRow = DiffLine | DiffGap;

// LCS table size guard (cells). The 20k-char cap allows ~10k one-char lines in theory; past this
// budget we show the middle as a full replace instead of allocating a huge table.
const MAX_LCS_CELLS = 4_000_000;
const CONTEXT_LINES = 2;

const sameLine = (text: string): DiffLine => ({ kind: "same", text });
const addedLine = (text: string): DiffLine => ({ kind: "added", text });
const removedLine = (text: string): DiffLine => ({ kind: "removed", text });

const splitLines = (text: string): string[] => (text === "" ? [] : text.split(/\r?\n/));

/** Diff of the lines that differ once the common head and tail are trimmed off. */
function diffMiddle(before: string[], after: string[]): DiffLine[] {
  if (before.length === 0) return after.map(addedLine);
  if (after.length === 0) return before.map(removedLine);
  if (before.length * after.length > MAX_LCS_CELLS) {
    return [...before.map(removedLine), ...after.map(addedLine)];
  }

  // lcs[i][j] = longest common subsequence of before[i:] and after[j:] (flattened). Uint16 is
  // safe: the LCS is bounded by min(before, after) <= sqrt(MAX_LCS_CELLS) = 2000.
  const width = after.length + 1;
  const lcs = new Uint16Array((before.length + 1) * width);
  for (let i = before.length - 1; i >= 0; i--) {
    for (let j = after.length - 1; j >= 0; j--) {
      lcs[i * width + j] =
        before[i] === after[j]
          ? lcs[(i + 1) * width + j + 1] + 1
          : Math.max(lcs[(i + 1) * width + j], lcs[i * width + j + 1]);
    }
  }

  const lines: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < before.length && j < after.length) {
    if (before[i] === after[j]) {
      lines.push(sameLine(before[i]));
      i++;
      j++;
    } else if (lcs[(i + 1) * width + j] >= lcs[i * width + j + 1]) {
      lines.push(removedLine(before[i++]));
    } else {
      lines.push(addedLine(after[j++]));
    }
  }
  while (i < before.length) lines.push(removedLine(before[i++]));
  while (j < after.length) lines.push(addedLine(after[j++]));
  return lines;
}

/** Lines of `before` -> `after`: "removed" exists only in `before`, "added" only in `after`. */
export function diffLines(before: string, after: string): DiffLine[] {
  const a = splitLines(before);
  const b = splitLines(after);

  let head = 0;
  while (head < a.length && head < b.length && a[head] === b[head]) head++;
  let tailA = a.length;
  let tailB = b.length;
  while (tailA > head && tailB > head && a[tailA - 1] === b[tailB - 1]) {
    tailA--;
    tailB--;
  }

  return [
    ...a.slice(0, head).map(sameLine),
    ...diffMiddle(a.slice(head, tailA), b.slice(head, tailB)),
    ...a.slice(tailA).map(sameLine),
  ];
}

export function hasChanges(lines: DiffLine[]): boolean {
  return lines.some((line) => line.kind !== "same");
}

/** Keeps `context` unchanged lines around each change and folds the rest into gaps. */
export function collapseUnchanged(lines: DiffLine[], context = CONTEXT_LINES): DiffRow[] {
  const visible = new Array<boolean>(lines.length).fill(false);
  lines.forEach((line, index) => {
    if (line.kind === "same") return;
    const from = Math.max(0, index - context);
    const to = Math.min(lines.length - 1, index + context);
    for (let k = from; k <= to; k++) visible[k] = true;
  });

  const rows: DiffRow[] = [];
  let hidden = 0;
  lines.forEach((line, index) => {
    if (visible[index]) {
      if (hidden > 0) rows.push({ kind: "gap", hiddenLines: hidden });
      hidden = 0;
      rows.push(line);
    } else {
      hidden++;
    }
  });
  if (hidden > 0) rows.push({ kind: "gap", hiddenLines: hidden });
  return rows;
}
