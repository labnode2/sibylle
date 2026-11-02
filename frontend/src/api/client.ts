// The typed API client: paths and payloads come from src/api/schema.d.ts (`npm run gen:api`).
import createClient, { type Middleware } from 'openapi-fetch';

import type { paths } from './schema';

export type ErrorBody = {
  error: { code: string; message: string; fields?: Record<string, string> };
};

/** An error answered by the server, with the contract's code (`already_bet`, `pseudo_taken`…). */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly fields: Record<string, string>;

  constructor(status: number, body: Partial<ErrorBody> | undefined) {
    super(body?.error?.message ?? `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.code = body?.error?.code ?? 'error';
    this.fields = body?.error?.fields ?? {};
  }
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

// Every request that changes something carries the header the server's CSRF check expects.
const csrf: Middleware = {
  onRequest({ request }) {
    if (!SAFE_METHODS.has(request.method)) request.headers.set('X-Sibylle', '1');
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: '', credentials: 'include' });
api.use(csrf);

type Result<T> = { data?: T; error?: unknown; response: Response };

/** The data of a response, or an ApiError. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok || error !== undefined) {
    throw new ApiError(response.status, error as Partial<ErrorBody> | undefined);
  }
  return data as T;
}
