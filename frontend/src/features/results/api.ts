import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { orgKey } from '../orgs/api';
import { pronoKey, pronoListKey, type PronoDetail } from '../pronos/api';

export type ResultIn = components['schemas']['ResultIn'];
export type RelaunchIn = components['schemas']['RelaunchIn'];
export type ReportIn = components['schemas']['ReportIn'];
export type SpecialEdition = components['schemas']['SpecialEditionOut'];

type Path = { params: { path: { org_id: string; prono_id: string } } };

/** A change of the prono's result or state: the answer is the new detail. */
function useResultAction<Body>(
  orgId: string,
  pronoId: string,
  success: string,
  send: (path: Path, body: Body) => Promise<PronoDetail>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Body) =>
      send({ params: { path: { org_id: orgId, prono_id: pronoId } } }, body),
    onSuccess: (detail) => {
      client.setQueryData(pronoKey(orgId, pronoId), detail);
      void client.invalidateQueries({ queryKey: pronoListKey(orgId) });
      void client.invalidateQueries({ queryKey: orgKey(orgId) });
    },
    meta: { success },
  });
}

export function useResolve(orgId: string, pronoId: string) {
  return useResultAction(orgId, pronoId, 'results:toast.resolved', (path, body: ResultIn) =>
    unwrap(api.POST('/api/orgs/{org_id}/pronos/{prono_id}/resolve', { ...path, body })),
  );
}

export function useCorrect(orgId: string, pronoId: string) {
  return useResultAction(orgId, pronoId, 'results:toast.corrected', (path, body: ResultIn) =>
    unwrap(api.POST('/api/orgs/{org_id}/pronos/{prono_id}/correct', { ...path, body })),
  );
}

export function useRelaunch(orgId: string, pronoId: string) {
  return useResultAction(orgId, pronoId, 'results:toast.relaunched', (path, body: RelaunchIn) =>
    unwrap(api.POST('/api/orgs/{org_id}/pronos/{prono_id}/relaunch', { ...path, body })),
  );
}

export function useCancel(orgId: string, pronoId: string) {
  return useResultAction(
    orgId,
    pronoId,
    'results:toast.cancelled',
    (path, body: { reason?: string | null }) =>
      unwrap(api.POST('/api/orgs/{org_id}/pronos/{prono_id}/cancel', { ...path, body })),
  );
}

export function useReport(orgId: string, pronoId: string) {
  return useMutation({
    mutationFn: (body: ReportIn) =>
      unwrap(
        api.POST('/api/orgs/{org_id}/pronos/{prono_id}/reports', {
          params: { path: { org_id: orgId, prono_id: pronoId } },
          body,
        }),
      ),
    meta: { success: 'results:report.sent' },
  });
}
