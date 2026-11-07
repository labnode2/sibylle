<#-- Confirme ton adresse: when the address must be confirmed before going on, or when the app asks
     for a new link. Not at sign-up: an unconfirmed account may play (spec FR-002). -->
<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("emailVerifyTitle")}
    <#elseif section = "form">
        <p class="lead"><#if verifyEmail??>${msg("emailVerifyInstruction1", verifyEmail)}<#else>${msg("emailVerifyInstruction4", user.email)}</#if></p>
        <#if isAppInitiatedAction??>
            <form id="kc-verify-email-form" class="actions" action="${url.loginAction}" method="post" novalidate>
                <#if verifyEmail??>
                    <button type="submit" class="button button-secondary">${msg("emailVerifyResend")}</button>
                <#else>
                    <button type="submit" class="button">${msg("emailVerifySend")}</button>
                </#if>
                <button type="submit" name="cancel-aia" value="true" class="button button-secondary" formnovalidate>${msg("doCancel")}</button>
            </form>
        <#else>
            <p class="lead">${msg("emailVerifyInstruction2")} <a href="${url.loginAction}">${msg("sibylle.resendLink")}</a></p>
        </#if>
    </#if>
</@layout.registrationLayout>
