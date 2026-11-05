import { ApiError } from './api';

export function errorText(err: unknown, fallback = 'Něco se nepovedlo'): string {
  if (err instanceof ApiError) return err.message;
  return fallback;
}
