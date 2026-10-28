/** Only paths inside this site are accepted as the place to return to after signing in. */
export function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//")
    ? value
    : "/";
}
