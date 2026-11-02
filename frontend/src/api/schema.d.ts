// Généré par `npm run gen:api` depuis l'OpenAPI du serveur. Ne pas modifier à la main.

export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/content": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Content */
        get: operations["get_content_api_content_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/signup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Signup */
        post: operations["signup_api_auth_signup_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/verify-email": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Email */
        post: operations["verify_email_api_auth_verify_email_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/verify-email/resend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resend Verification */
        post: operations["resend_verification_api_auth_verify_email_resend_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/password-reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Request Password Reset */
        post: operations["request_password_reset_api_auth_password_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/password-reset/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm Password Reset */
        post: operations["confirm_password_reset_api_auth_password_reset_confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Me */
        get: operations["get_me_api_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Me */
        patch: operations["update_me_api_me_patch"];
        trace?: never;
    };
    "/api/me/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Change Password */
        post: operations["change_password_api_me_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Org */
        post: operations["create_org_api_orgs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Org */
        get: operations["get_org_api_orgs__org_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/members": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Members */
        get: operations["list_members_api_orgs__org_id__members_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/members/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update My Profile */
        patch: operations["update_my_profile_api_orgs__org_id__members_me_patch"];
        trace?: never;
    };
    "/api/orgs/{org_id}/members/{member_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Member */
        get: operations["get_member_api_orgs__org_id__members__member_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/invitations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Invitation */
        post: operations["create_invitation_api_orgs__org_id__invitations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/join/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Join */
        post: operations["preview_join_api_join_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/join": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Join */
        post: operations["join_api_join_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/sections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Sections */
        get: operations["list_sections_api_orgs__org_id__sections_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/pronos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Pronos */
        get: operations["list_pronos_api_orgs__org_id__pronos_get"];
        put?: never;
        /** Create Prono */
        post: operations["create_prono_api_orgs__org_id__pronos_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/pronos/{prono_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Prono */
        get: operations["get_prono_api_orgs__org_id__pronos__prono_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Edit Prono */
        patch: operations["edit_prono_api_orgs__org_id__pronos__prono_id__patch"];
        trace?: never;
    };
    "/api/orgs/{org_id}/pronos/{prono_id}/bets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Place Bet */
        post: operations["place_bet_api_orgs__org_id__pronos__prono_id__bets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/pronos/{prono_id}/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resolve */
        post: operations["resolve_api_orgs__org_id__pronos__prono_id__resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/pronos/{prono_id}/correct": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Correct */
        post: operations["correct_api_orgs__org_id__pronos__prono_id__correct_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/pronos/{prono_id}/relaunch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Relaunch */
        post: operations["relaunch_api_orgs__org_id__pronos__prono_id__relaunch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/pronos/{prono_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel */
        post: operations["cancel_api_orgs__org_id__pronos__prono_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/pronos/{prono_id}/reports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Report */
        post: operations["create_report_api_orgs__org_id__pronos__prono_id__reports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/uploads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Image */
        post: operations["upload_image_api_orgs__org_id__uploads_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/orgs/{org_id}/uploads/{upload_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Image */
        get: operations["get_image_api_orgs__org_id__uploads__upload_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** BetIn */
        BetIn: {
            /** Option Id */
            option_id?: string | null;
            /** Number Value */
            number_value?: number | string | null;
            /** Date Value */
            date_value?: string | null;
            /** Stake */
            stake: number;
        };
        /** BetOut */
        BetOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            member: components["schemas"]["MemberPublic"];
            /** Option Id */
            option_id: string | null;
            /** Number Value */
            number_value: string | null;
            /** Date Value */
            date_value: string | null;
            /** Answer */
            answer: string;
            /** Stake */
            stake: number;
            /** Rank */
            rank: number;
            /**
             * Placed At
             * Format: date-time
             */
            placed_at: string;
            /** Superseded */
            superseded: boolean;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "pending" | "won" | "lost" | "refunded";
            /** Payout */
            payout: number;
        };
        /** Body_upload_image_api_orgs__org_id__uploads_post */
        Body_upload_image_api_orgs__org_id__uploads_post: {
            /** File */
            file: string;
        };
        /** BucketOut */
        BucketOut: {
            /** Label */
            label: string;
            /** Count */
            count: number;
            /** Stake Total */
            stake_total: number;
            /** Share Pct */
            share_pct: number;
        };
        /** CancelIn */
        CancelIn: {
            /** Reason */
            reason?: string | null;
        };
        /** Content */
        Content: {
            /** Avatars */
            avatars: components["schemas"]["Template"][];
            /** Logos */
            logos: components["schemas"]["Template"][];
            /** Backgrounds */
            backgrounds: string[];
            /** Charter */
            charter: string;
        };
        /** EmailInvitationIn */
        EmailInvitationIn: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "email";
            /** Email */
            email: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** Health */
        Health: {
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "error";
            /**
             * Db
             * @enum {string}
             */
            db: "ok" | "error";
        };
        /** InvitationCreated */
        InvitationCreated: {
            invitation: components["schemas"]["InvitationOut"];
            /** Url */
            url: string | null;
        };
        /** InvitationOut */
        InvitationOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "link" | "email";
            /** Email */
            email: string | null;
            /** Max Uses */
            max_uses: number;
            /** Use Count */
            use_count: number;
            /** Places Left */
            places_left: number;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Revoked At */
            revoked_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** JoinIn */
        JoinIn: {
            /** Token */
            token?: string | null;
            /** Code */
            code?: string | null;
            /** Pseudo */
            pseudo: string;
            avatar: components["schemas"]["PixelImage"];
            /**
             * Charter Accepted
             * @constant
             */
            charter_accepted: true;
        };
        /** JoinPreview */
        JoinPreview: {
            org: components["schemas"]["OrgCard"];
            /** Member Count */
            member_count: number;
            /** Places Left */
            places_left: number | null;
            /** Invited By Pseudo */
            invited_by_pseudo: string | null;
            /** Charter */
            charter: string;
            /** Already Member */
            already_member: boolean;
        };
        /** JoinSource */
        JoinSource: {
            /** Token */
            token?: string | null;
            /** Code */
            code?: string | null;
        };
        /** Joined */
        Joined: {
            org: components["schemas"]["OrgCard"];
            membership: components["schemas"]["MemberSelf"];
        };
        /** LinkInvitationIn */
        LinkInvitationIn: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "link";
            /** Max Uses */
            max_uses: number;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
        };
        /** LoginIn */
        LoginIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** Me */
        Me: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Email */
            email: string;
            /** First Name */
            first_name: string;
            /** Last Name */
            last_name: string;
            /** Email Verified */
            email_verified: boolean;
            /**
             * Theme
             * @enum {string}
             */
            theme: "auto" | "light" | "dark";
            /** Reduce Motion */
            reduce_motion: boolean;
            /** Locale */
            locale: string;
            /** Memberships */
            memberships: components["schemas"]["MembershipEntry"][];
        };
        /** MePatch */
        MePatch: {
            /** First Name */
            first_name?: string | null;
            /** Last Name */
            last_name?: string | null;
            /** Theme */
            theme?: ("auto" | "light" | "dark") | null;
            /** Reduce Motion */
            reduce_motion?: boolean | null;
            /** Locale */
            locale?: "fr" | null;
        };
        /** MemberPatch */
        MemberPatch: {
            /** Pseudo */
            pseudo?: string | null;
            avatar?: components["schemas"]["PixelImage"] | null;
        };
        /** MemberPublic */
        MemberPublic: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Pseudo */
            pseudo: string;
            avatar: components["schemas"]["PixelImage"];
            /** Frame */
            frame?: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "reader" | "journalist" | "editor";
            /**
             * Joined At
             * Format: date-time
             */
            joined_at: string;
        };
        /** MemberSelf */
        MemberSelf: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Pseudo */
            pseudo: string;
            avatar: components["schemas"]["PixelImage"];
            /** Frame */
            frame?: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "reader" | "journalist" | "editor";
            /**
             * Joined At
             * Format: date-time
             */
            joined_at: string;
            /** Balance */
            balance: number;
            /** Season Score */
            season_score: number;
            /**
             * Unlocked Colors
             * @default []
             */
            unlocked_colors: number[];
        };
        /** MembershipEntry */
        MembershipEntry: {
            org: components["schemas"]["OrgCard"];
            membership: components["schemas"]["MemberSelf"];
        };
        /** OptionOut */
        OptionOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Label */
            label: string;
            /** Is Correct */
            is_correct: boolean | null;
            /** Count */
            count: number;
            /** Stake Total */
            stake_total: number;
            /** Share Pct */
            share_pct: number;
        };
        /** Org */
        Org: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string;
            logo: components["schemas"]["PixelImage"] | null;
            /** Background Key */
            background_key: string;
            /** Starting Balance */
            starting_balance: number;
            /** Max Base Gain */
            max_base_gain: number;
            /** Early Bird Pct */
            early_bird_pct: number;
            /** Early Bird Count */
            early_bird_count: number;
            /** Editor Note */
            editor_note: string | null;
            /** Charter */
            charter: string;
            /** Access Code */
            access_code: string | null;
            /** Member Count */
            member_count: number;
            my_membership: components["schemas"]["MemberSelf"];
        };
        /** OrgCard */
        OrgCard: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string;
            logo: components["schemas"]["PixelImage"] | null;
            /** Background Key */
            background_key: string;
        };
        /** OrgCreated */
        OrgCreated: {
            org: components["schemas"]["Org"];
            membership: components["schemas"]["MemberSelf"];
        };
        /** OrgIn */
        OrgIn: {
            /** Title */
            title: string;
            /** Background Key */
            background_key: string;
            logo?: components["schemas"]["PixelImage"] | null;
            /** Pseudo */
            pseudo: string;
            avatar: components["schemas"]["PixelImage"];
        };
        /** PasswordChange */
        PasswordChange: {
            /** Current Password */
            current_password: string;
            /** New Password */
            new_password: string;
        };
        /** PixelImage */
        PixelImage: {
            /**
             * Size
             * @enum {integer}
             */
            size: 16 | 32;
            /**
             * Palette
             * @constant
             */
            palette: "base-v1";
            /** Pixels */
            pixels: string;
        };
        /** PronoDetail */
        PronoDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "choice" | "yes_no" | "number" | "date";
            /** Question */
            question: string;
            section: components["schemas"]["SectionOut"];
            /**
             * State
             * @enum {string}
             */
            state: "proposed" | "rejected" | "scheduled" | "open" | "closed" | "resolved" | "cancelled";
            /** Base Gain */
            base_gain: number;
            /** Opens At */
            opens_at: string | null;
            /** Closes At */
            closes_at: string | null;
            /** Open Ended */
            open_ended: boolean;
            /** Result Expected At */
            result_expected_at: string | null;
            /** Number Unit */
            number_unit: string | null;
            /** Link Url */
            link_url: string | null;
            /** Image Url */
            image_url: string | null;
            /** Bet Count */
            bet_count: number;
            /** Pot */
            pot: number;
            /** Relaunch Count */
            relaunch_count: number;
            created_by: components["schemas"]["MemberPublic"];
            /** Options */
            options: components["schemas"]["OptionOut"][];
            /** Distribution */
            distribution: components["schemas"]["BucketOut"][];
            /** Bets */
            bets: components["schemas"]["BetOut"][];
            my_bet: components["schemas"]["BetOut"] | null;
            /** Can Rebet */
            can_rebet: boolean;
            /** Can Edit */
            can_edit: boolean;
            /** Reactions */
            reactions: {
                [key: string]: number;
            };
            /** My Reactions */
            my_reactions: string[];
            /** Events */
            events: components["schemas"]["PronoEventOut"][];
            special_edition?: components["schemas"]["SpecialEditionOut"] | null;
        };
        /** PronoEventOut */
        PronoEventOut: {
            /** Kind */
            kind: string;
            /**
             * At
             * Format: date-time
             */
            at: string;
            /** Data */
            data: {
                [key: string]: unknown;
            };
        };
        /** PronoIn */
        PronoIn: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "choice" | "yes_no" | "number" | "date";
            /** Question */
            question: string;
            /**
             * Section Id
             * Format: uuid
             */
            section_id: string;
            /** Options */
            options?: string[];
            /** Base Gain */
            base_gain: number;
            /** Link Url */
            link_url?: string | null;
            /** Image Id */
            image_id?: string | null;
            /** Opens At */
            opens_at?: string | null;
            /** Closes At */
            closes_at?: string | null;
            /**
             * Open Ended
             * @default false
             */
            open_ended: boolean;
            /** Result Expected At */
            result_expected_at?: string | null;
            /** Number Unit */
            number_unit?: string | null;
        };
        /** PronoList */
        PronoList: {
            /** Items */
            items: components["schemas"]["PronoSummary"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** PronoPatch */
        PronoPatch: {
            /** Kind */
            kind?: ("choice" | "yes_no" | "number" | "date") | null;
            /** Question */
            question?: string | null;
            /** Section Id */
            section_id?: string | null;
            /** Options */
            options?: string[] | null;
            /** Base Gain */
            base_gain?: number | null;
            /** Link Url */
            link_url?: string | null;
            /** Image Id */
            image_id?: string | null;
            /** Opens At */
            opens_at?: string | null;
            /** Closes At */
            closes_at?: string | null;
            /** Open Ended */
            open_ended?: boolean | null;
            /** Result Expected At */
            result_expected_at?: string | null;
            /** Number Unit */
            number_unit?: string | null;
        };
        /** PronoSummary */
        PronoSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "choice" | "yes_no" | "number" | "date";
            /** Question */
            question: string;
            section: components["schemas"]["SectionOut"];
            /**
             * State
             * @enum {string}
             */
            state: "proposed" | "rejected" | "scheduled" | "open" | "closed" | "resolved" | "cancelled";
            /** Base Gain */
            base_gain: number;
            /** Opens At */
            opens_at: string | null;
            /** Closes At */
            closes_at: string | null;
            /** Open Ended */
            open_ended: boolean;
            /** Result Expected At */
            result_expected_at: string | null;
            /** Number Unit */
            number_unit: string | null;
            /** Link Url */
            link_url: string | null;
            /** Image Url */
            image_url: string | null;
            /** Bet Count */
            bet_count: number;
            /** Pot */
            pot: number;
            /** Relaunch Count */
            relaunch_count: number;
            created_by: components["schemas"]["MemberPublic"];
        };
        /** RelaunchIn */
        RelaunchIn: {
            /**
             * Closes At
             * Format: date-time
             */
            closes_at: string;
            /** Result Expected At */
            result_expected_at?: string | null;
            /** Reason */
            reason?: string | null;
        };
        /** ReportIn */
        ReportIn: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "result_error" | "content";
            /** Message */
            message?: string | null;
        };
        /** ReportOut */
        ReportOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Prono Id
             * Format: uuid
             */
            prono_id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "result_error" | "content";
            /** Message */
            message: string | null;
            /**
             * State
             * @enum {string}
             */
            state: "open" | "resolved" | "dismissed";
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** ResetConfirm */
        ResetConfirm: {
            /** Token */
            token: string;
            /** Password */
            password: string;
        };
        /** ResetRequest */
        ResetRequest: {
            /** Email */
            email: string;
        };
        /**
         * ResultIn
         * @description The correct options of a choice or yes/no prono, or the real number or date.
         */
        ResultIn: {
            /** Correct Option Ids */
            correct_option_ids?: string[] | null;
            /** Result Number */
            result_number?: number | string | null;
            /** Result Date */
            result_date?: string | null;
        };
        /** SectionOut */
        SectionOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Position */
            position: number;
        };
        /** SignupIn */
        SignupIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
            /** First Name */
            first_name: string;
            /** Last Name */
            last_name: string;
        };
        /**
         * SpecialEditionOut
         * @description The published result of a prono: who won what, and whether the pot was lost.
         */
        SpecialEditionOut: {
            /** Settlement Seq */
            settlement_seq: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "resolution" | "correction" | "cancellation";
            /** Result */
            result: string | null;
            /**
             * Settled At
             * Format: date-time
             */
            settled_at: string;
            /** Pot */
            pot: number;
            /** Pot Lost */
            pot_lost: boolean;
            /** Winners */
            winners: components["schemas"]["WinnerOut"][];
        };
        /** Template */
        Template: {
            /** Key */
            key: string;
            /** Name */
            name: string;
            image: components["schemas"]["PixelImage"];
        };
        /** TokenIn */
        TokenIn: {
            /** Token */
            token: string;
        };
        /** UploadOut */
        UploadOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Width */
            width: number;
            /** Height */
            height: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** WinnerOut */
        WinnerOut: {
            member: components["schemas"]["MemberPublic"];
            /**
             * Bet Id
             * Format: uuid
             */
            bet_id: string;
            /** Stake */
            stake: number;
            /** Payout */
            payout: number;
            /** Base Gain */
            base_gain: number;
            /** Early Bird */
            early_bird: number;
            /** Pot Share */
            pot_share: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
        };
    };
    get_content_api_content_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Content"];
                };
            };
        };
    };
    signup_api_auth_signup_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignupIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Me"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Me"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    verify_email_api_auth_verify_email_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TokenIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resend_verification_api_auth_verify_email_resend_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    request_password_reset_api_auth_password_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirm_password_reset_api_auth_password_reset_confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResetConfirm"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_me_api_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Me"];
                };
            };
        };
    };
    update_me_api_me_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MePatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Me"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    change_password_api_me_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordChange"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_org_api_orgs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrgIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrgCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_org_api_orgs__org_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Org"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_members_api_orgs__org_id__members_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberPublic"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_my_profile_api_orgs__org_id__members_me_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MemberPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberSelf"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_member_api_orgs__org_id__members__member_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                member_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_invitation_api_orgs__org_id__invitations_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LinkInvitationIn"] | components["schemas"]["EmailInvitationIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvitationCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_join_api_join_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JoinSource"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JoinPreview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    join_api_join_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JoinIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Joined"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sections_api_orgs__org_id__sections_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SectionOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_pronos_api_orgs__org_id__pronos_get: {
        parameters: {
            query?: {
                state?: string[];
                section?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: never;
            path: {
                org_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PronoList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_prono_api_orgs__org_id__pronos_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PronoIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PronoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_prono_api_orgs__org_id__pronos__prono_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                prono_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PronoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_prono_api_orgs__org_id__pronos__prono_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                prono_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PronoPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PronoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    place_bet_api_orgs__org_id__pronos__prono_id__bets_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                prono_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BetIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BetOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_api_orgs__org_id__pronos__prono_id__resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                prono_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResultIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PronoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    correct_api_orgs__org_id__pronos__prono_id__correct_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                prono_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResultIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PronoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    relaunch_api_orgs__org_id__pronos__prono_id__relaunch_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                prono_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RelaunchIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PronoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_api_orgs__org_id__pronos__prono_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                prono_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CancelIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PronoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_report_api_orgs__org_id__pronos__prono_id__reports_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                prono_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReportIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_image_api_orgs__org_id__uploads_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_image_api_orgs__org_id__uploads_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_image_api_orgs__org_id__uploads__upload_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                org_id: string;
                upload_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
