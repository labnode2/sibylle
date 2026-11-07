<#-- Nouveau mot de passe (frontend/src/features/auth/AuthPages.tsx, ResetPasswordPage): after the
     e-mail's link, or when the app asks for a new password (then « Annuler » goes back to it). The
     other devices are signed out unless the box is unticked. Keycloak gives a refused password
     (too short…) as the page's message: it shows under the field, as in the app. -->
<#import "template.ftl" as layout>
<#import "field.ftl" as field>
<#assign passwordError = field.errorOf('password')>
<#assign pageError = ((message.type)!'') == 'error' && !messagesPerField.existsError('password-confirm')>
<#if pageError && !passwordError?has_content>
    <#assign passwordError = message.summary>
</#if>
<@layout.registrationLayout displayMessage=!pageError && !messagesPerField.existsError('password', 'password-confirm'); section>
    <#if section = "header">
        ${msg("updatePasswordTitle")}
    <#elseif section = "form">
        <form id="kc-passwd-update-form" class="form" action="${url.loginAction}" method="post" novalidate>
            <@field.newPassword name="password-new" label=msg("passwordNew") hint=msg("sibylle.passwordHint") error=passwordError confirmError=field.errorOf('password-confirm') autofocus=true/>
            <label class="checkbox">
                <input type="checkbox" id="logout-sessions" name="logout-sessions" value="on" checked>
                ${msg("logoutOtherSessions")}
            </label>
            <#if isAppInitiatedAction??>
                <div class="actions">
                    <button type="submit" name="login" class="button">${msg("sibylle.passwordSubmit")}</button>
                    <button type="submit" name="cancel-aia" value="true" class="button button-secondary" formnovalidate>${msg("doCancel")}</button>
                </div>
            <#else>
                <button type="submit" name="login" class="button button-block">${msg("sibylle.passwordSubmit")}</button>
            </#if>
        </form>
    </#if>
</@layout.registrationLayout>
