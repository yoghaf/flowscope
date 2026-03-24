const USER_ID_KEY = "flowscope_user_id";

function generateId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function getUserId(): string {
  if (typeof window === "undefined") {
    return "local";
  }

  const existing = window.localStorage.getItem(USER_ID_KEY);
  if (existing) {
    return existing;
  }

  const value = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : generateId();
  window.localStorage.setItem(USER_ID_KEY, value);
  return value;
}
