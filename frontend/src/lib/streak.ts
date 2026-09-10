/**
 * The line under a streak count. "3 to 3" read as nonsense for a new user (3 days remaining
 * until the 3-day milestone), so the milestone is named as what it is: a run of that length.
 */
export function streakSubtitle(current: number, nextMilestone: number | null, longest: number): string {
  if (!nextMilestone) return `best ${longest}`;
  const left = nextMilestone - current;
  return `${left} day${left === 1 ? "" : "s"} to a ${nextMilestone}-day run`;
}
