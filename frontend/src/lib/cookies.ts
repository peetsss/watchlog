export function getCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const chunk of document.cookie.split(";")) {
    const value = chunk.trim();
    if (value.startsWith(prefix)) {
      return decodeURIComponent(value.slice(prefix.length));
    }
  }
  return null;
}
