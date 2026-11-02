import { QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { PreferencesProvider } from './preferences';
import { queryClient } from './queryClient';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <PreferencesProvider>{children}</PreferencesProvider>
    </QueryClientProvider>
  );
}
