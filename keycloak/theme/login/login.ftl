<#-- Connexion (frontend/src/features/auth/AuthPages.tsx, LoginPage): the e-mail, the password and
     the button, then « Créer un compte » and « Mot de passe oublié ? ». « EMILE » stands in big above
     the form. A wrong password shows as
     the frame's note, both fields marked. -->
<#import "template.ftl" as layout>
<#import "field.ftl" as field>
<#import "passkeys.ftl" as passkeys>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("loginAccountTitle")}
    <#elseif section = "form">
        <p class="emile" id="kc-emile">EMILE</p>
        <#if realm.password>
            <#assign invalid = messagesPerField.existsError('username', 'password')>
            <form id="kc-form-login" class="form" action="${url.loginAction}" method="post" novalidate>
                <#if !usernameHidden??>
                    <#assign usernameAutocomplete = "username">
                    <#if enableWebAuthnConditionalUI?has_content><#assign usernameAutocomplete = "username webauthn"></#if>
                    <@field.input name="username" label=field.usernameLabel() type=realm.registrationEmailAsUsername?then("email", "text") value=(login.username!'') autocomplete=usernameAutocomplete autofocus=true dir="ltr" invalid=invalid/>
                </#if>
                <@field.input name="password" label=msg("password") type="password" autocomplete="current-password" autofocus=usernameHidden?? invalid=invalid/>
                <#if realm.rememberMe && !usernameHidden??>
                    <label class="checkbox">
                        <input id="rememberMe" name="rememberMe" type="checkbox"<#if login.rememberMe??> checked</#if>>
                        ${msg("rememberMe")}
                    </label>
                </#if>
                <input type="hidden" id="id-hidden-input" name="credentialId"<#if auth.selectedCredential?has_content> value="${auth.selectedCredential}"</#if>>
                <button type="submit" id="kc-login" name="login" class="button button-block">${msg("doLogIn")}</button>
            </form>
            <@passkeys.conditionalUIData/>
        </#if>
        <#assign canRegister = realm.password && realm.registrationAllowed && !registrationDisabled??>
        <#if canRegister || realm.resetPasswordAllowed>
            <div class="links">
                <#if canRegister><a href="${url.registrationUrl}">${msg("doRegister")}</a></#if>
                <#if realm.resetPasswordAllowed><a href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a></#if>
            </div>
        </#if>
    <#elseif section = "socialProviders">
        <#if realm.password && social?? && social.providers?has_content>
            <div id="kc-social-providers" class="form">
                <p class="kicker">${msg("identity-provider-login-label")}</p>
                <#list social.providers as p>
                    <a data-once-link id="social-${p.alias}" class="button button-secondary button-block" href="${p.loginUrl}">${p.displayName!}</a>
                </#list>
            </div>
        </#if>
    </#if>
</@layout.registrationLayout>
