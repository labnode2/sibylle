// Short names for the API's schemas (generated in schema.d.ts).
import type { components } from './schema';

type Schemas = components['schemas'];

export type Me = Schemas['Me'];
export type MemberPublic = Schemas['MemberPublic'];
export type MemberSelf = Schemas['MemberSelf'];
export type OrgCard = Schemas['OrgCard'];
export type Org = Schemas['Org'];
export type Content = Schemas['Content'];
export type Template = Schemas['Template'];
export type JoinPreview = Schemas['JoinPreview'];
export type InvitationCreated = Schemas['InvitationCreated'];
export type PixelImage = Schemas['PixelImage'];
