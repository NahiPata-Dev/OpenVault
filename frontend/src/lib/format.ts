export function formatIST(value: string | null | undefined): string {
  if (!value) return "Not provided";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(date);
}

export function istInputToISO(value: string): string {
  const date = new Date(`${value}:00+05:30`);
  if (Number.isNaN(date.getTime())) {
    throw new Error("Enter a valid date and time in IST.");
  }
  return date.toISOString();
}

export function istDateEndToISO(value: string): string {
  const date = new Date(`${value}T23:59:59+05:30`);
  if (Number.isNaN(date.getTime())) {
    throw new Error("Enter a valid end date in IST.");
  }
  return date.toISOString();
}

export function formatWindow(window: { weekday: number; start: string; end: string }): string {
  const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  return `${weekdays[window.weekday - 1] ?? `Day ${window.weekday}`} · ${window.start}–${window.end} IST`;
}

export function statusLabel(status: string): string {
  return status.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
