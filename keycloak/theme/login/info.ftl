<#-- A word from Keycloak and the way on, like the app's address check
     (frontend/src/features/auth/AuthPages.tsx, VerifyEmailPage): the address confirmed, the
     account updated, a link from an e-mail to confirm first… The message is the title; a page
     that has a title of its own shows the message under it. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if messageHeader??>${kcSanitize(msg("${messageHeader}"))?no_esc}<#else>${kcSanitize(message.summary)?no_esc}</#if>
    <#elseif section = "form">
        <div id="kc-info-message" class="form">
            <#if messageHeader??>
                <p class="lead">${kcSanitize(message.summary)?no_esc}</p>
            </#if>
            <#if requiredActions??>
                <p class="lead"><#list requiredActions as reqActionItem><strong>${msg("requiredAction.${reqActionItem}")}</strong><#sep>, </#list></p>
            </#if>
            <#if !skipLink??>
                <#if pageRedirectUri?has_content>
                    <a href="${pageRedirectUri}">${msg("backToApplication")}</a>
                <#elseif actionUri?has_content>
                    <a class="button button-block" href="${actionUri}">${msg("proceedWithAction")}</a>
                <#elseif (client.baseUrl)?has_content>
                    <a href="${client.baseUrl}">${msg("backToApplication")}</a>
                </#if>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
