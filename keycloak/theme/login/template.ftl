<#-- The frame of every sign-in page, like the app's public pages (frontend/src/app/router.tsx,
     PublicPage): the masthead and its double rule, then the page's column
     (frontend/src/features/auth/AuthPages.tsx) with its title, Keycloak's message as one of the
     app's notes, and the page itself. The base theme's pages that Sibylle does not rewrite get
     this frame too. The macro and its sections are the base theme's (base/login/template.ftl). -->
<#import "footer.ftl" as loginFooter>
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<#assign header><#nested "header"></#assign>
<#assign header = header?markup_string?trim?no_esc>
<!DOCTYPE html>
<html lang="${lang}"<#if realm.internationalizationEnabled> dir="${(locale.rtl)?then('rtl','ltr')}"</#if>>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="robots" content="noindex, nofollow">
    <title>${header} · ${msg("sibylle.name")}</title>
    <link rel="icon" href="${url.resourcesPath}/img/favicon.svg" type="image/svg+xml">
    <link rel="icon" href="${url.resourcesPath}/img/favicon.ico" sizes="16x16 32x32 48x48">
    <link rel="apple-touch-icon" href="${url.resourcesPath}/img/apple-touch-icon.png">
    <#list (properties.styles!'')?split(' ') as style>
        <#if style?has_content><link href="${url.resourcesPath}/${style}" rel="stylesheet"></#if>
    </#list>
    <#-- For the base theme's passkey pages (webauthnAuthenticate.js). -->
    <script type="importmap">
        {
            "imports": {
                "rfc4648": "${url.resourcesCommonPath}/vendor/rfc4648/rfc4648.js"
            }
        }
    </script>
    <script type="module" src="${url.resourcesPath}/js/sibylle.js"></script>
    <#if scripts??>
        <#list scripts as script>
            <script src="${script}" type="text/javascript"></script>
        </#list>
    </#if>
    <#-- The base theme's checks: a sign-in finished in another tab moves this one on, and a
         page from an old sign-in attempt reloads. -->
    <script type="module">
        <#outputformat "JavaScript">
        import { startSessionPolling } from ${(url.resourcesPath + "/js/authChecker.js")?c};

        startSessionPolling(${url.ssoLoginInOtherTabsUrl?c});
        </#outputformat>
    </script>
    <#if authenticationSession??>
        <script type="module">
            <#outputformat "JavaScript">
            import { checkAuthSession } from ${(url.resourcesPath + "/js/authChecker.js")?c};

            checkAuthSession(${authenticationSession.authSessionIdHash?c});
            </#outputformat>
        </script>
    </#if>
</head>

<body<#if bodyClass?has_content> class="${bodyClass}"</#if> data-page-id="login-${pageId}">
<div class="page">
    <header class="masthead">
        <canvas class="masthead-ball" width="16" height="16" role="img" aria-label="${msg("sibylle.ball")}" data-crystal-ball></canvas>
        <div class="masthead-title">
            <span class="masthead-kicker">${msg("sibylle.kicker")}</span>
            <span class="masthead-name">${msg("sibylle.name")}</span>
        </div>
    </header>
    <div class="rule-double" aria-hidden="true"></div>
    <main class="main">
        <section class="auth" aria-labelledby="kc-page-title">
            <h1 class="title" id="kc-page-title">${header}</h1>

            <#if auth?has_content && auth.showUsername() && !auth.showResetCredentials()>
                <#nested "show-username">
                <p class="attempted">
                    <span>${msg("sibylle.account")} <strong id="kc-attempted-username">${auth.attemptedUsername}</strong></span>
                    <a id="reset-login" href="${url.loginRestartFlowUrl}">${msg("restartLoginTooltip")}</a>
                </p>
            </#if>

            <#-- An app-initiated action does not show the warning that asks to complete it. The
                 mark, in the app's 12 × 12 pixel icons (frontend/src/ui/icons.ts): the check for
                 what went well, the cross for an error, « ! » and « i » for the rest. -->
            <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
                <div class="alert alert-${message.type}" role="${(message.type == 'error')?then('alert', 'status')}">
                    <span class="alert-mark" aria-hidden="true">
                        <svg width="12" height="12" viewBox="0 0 12 12" shape-rendering="crispEdges">
                            <#if message.type == 'error'>
                                <path fill="currentColor" d="M2 2h2v1h-2zM8 2h2v1h-2zM3 3h2v1h-2zM7 3h2v1h-2zM4 4h4v1h-4zM5 5h2v1h-2zM4 6h4v1h-4zM3 7h2v1h-2zM7 7h2v1h-2zM2 8h2v1h-2zM8 8h2v1h-2z"/>
                            <#elseif message.type == 'warning'>
                                <path fill="currentColor" d="M5 1h2v7h-2zM5 9h2v2h-2z"/>
                            <#elseif message.type == 'info'>
                                <path fill="currentColor" d="M5 1h2v2h-2zM5 4h2v7h-2z"/>
                            <#else>
                                <path fill="currentColor" d="M10 2h2v1h-2zM9 3h2v1h-2zM8 4h2v1h-2zM0 5h2v1h-2zM7 5h2v1h-2zM1 6h2v1h-2zM6 6h2v1h-2zM2 7h2v1h-2zM5 7h2v1h-2zM3 8h3v1h-3zM4 9h1v1h-1z"/>
                            </#if>
                        </svg>
                    </span>
                    <p class="alert-text">${kcSanitize(message.summary)?no_esc}</p>
                </div>
            </#if>

            <#nested "form">

            <#if auth?has_content && auth.showTryAnotherWayLink()>
                <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post" novalidate>
                    <input type="hidden" name="tryAnotherWay" value="on">
                    <button type="submit" id="try-another-way" class="button button-link">${msg("doTryAnotherWay")}</button>
                </form>
            </#if>

            <#if switchOrganizationEnabled?? && switchOrganizationEnabled>
                <form id="kc-switch-organization-form" action="${url.loginAction}" method="post" novalidate>
                    <input type="hidden" name="switchOrganization" value="true">
                    <button type="submit" id="switch-organization" class="button button-link">${msg("doSwitchOrganization")}</button>
                </form>
            </#if>

            <#nested "socialProviders">

            <#if displayInfo>
                <div id="kc-info" class="lead">
                    <#nested "info">
                </div>
            </#if>

            <@loginFooter.content/>
        </section>
    </main>
</div>
</body>
</html>
</#macro>
