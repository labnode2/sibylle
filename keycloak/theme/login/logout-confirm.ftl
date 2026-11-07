<#-- « Te déconnecter ? » (frontend/src/features/auth/LogoutDialog.tsx): Keycloak asks again when a
     sign-out reaches it without the proof of who asks. The way out in red, then the way back. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("logoutConfirmTitle")}
    <#elseif section = "form">
        <p class="lead">${msg("logoutConfirmHeader")}</p>
        <form id="kc-logout-confirm" class="actions" action="${url.logoutConfirmAction}" method="post" novalidate>
            <input type="hidden" name="session_code" value="${logoutConfirm.code}">
            <button type="submit" name="confirmLogout" id="kc-logout" value="${msg("doLogout")}" class="button button-danger">${msg("doLogout")}</button>
        </form>
        <#if !logoutConfirm.skipLink && (client.baseUrl)?has_content>
            <a href="${client.baseUrl}">${msg("backToApplication")}</a>
        </#if>
    </#if>
</@layout.registrationLayout>
