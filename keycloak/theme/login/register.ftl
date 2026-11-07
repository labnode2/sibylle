<#-- Créer un compte (frontend/src/features/auth/AuthPages.tsx, SignupPage): a word on the account,
     first and last names side by side with the note that they stay private, the e-mail, the
     password, then « J'ai déjà un compte ». Field errors show under their field. -->
<#import "template.ftl" as layout>
<#import "field.ftl" as field>
<#import "register-commons.ftl" as registerCommons>
<@layout.registrationLayout displayMessage=messagesPerField.exists('global'); section>
    <#if section = "header">
        <#if messageHeader??>${kcSanitize(msg("${messageHeader}"))?no_esc}<#else>${msg("registerTitle")}</#if>
    <#elseif section = "form">
        <p class="lead">${msg("sibylle.signupLead")}</p>
        <form id="kc-register-form" class="form" action="${url.registrationAction}" method="post" novalidate>
            <@field.profileFields>
                <#if passwordRequired??>
                    <@field.newPassword name="password" label=msg("password") hint=msg("sibylle.passwordHint") error=field.errorOf('password') confirmError=field.errorOf('password-confirm')/>
                </#if>
            </@field.profileFields>
            <@registerCommons.termsAcceptance/>
            <button type="submit" class="button button-block">${msg("sibylle.signupSubmit")}</button>
        </form>
        <div class="links">
            <a href="${url.loginUrl}">${msg("sibylle.haveAccount")}</a>
        </div>
    </#if>
</@layout.registrationLayout>
