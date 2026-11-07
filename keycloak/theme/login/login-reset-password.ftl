<#-- Mot de passe oublié (frontend/src/features/auth/AuthPages.tsx, ForgotPasswordPage): a word on
     what happens, the e-mail and « Recevoir le lien », then the way back. Keycloak then shows the
     sign-in page with its note: a link has left, if the account exists. -->
<#import "template.ftl" as layout>
<#import "field.ftl" as field>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username'); section>
    <#if section = "header">
        ${msg("emailForgotTitle")}
    <#elseif section = "form">
        <form id="kc-reset-password-form" class="form" action="${url.loginAction}" method="post" novalidate>
            <p class="lead">${msg("sibylle.forgotLead")}</p>
            <@field.input name="username" label=field.usernameLabel() type=realm.registrationEmailAsUsername?then("email", "text") value=(auth.attemptedUsername!'') autocomplete="username" autofocus=true dir="ltr" error=field.errorOf('username')/>
            <button type="submit" class="button button-block">${msg("sibylle.forgotSubmit")}</button>
        </form>
        <a href="${url.loginUrl}">${msg("backToLogin")}</a>
    </#if>
</@layout.registrationLayout>
