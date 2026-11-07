<#-- Something went wrong (a link that expired, a request Keycloak refuses): what happened, then the
     way back to the app. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        ${msg("errorTitle")}
    <#elseif section = "form">
        <div id="kc-error-message" class="form">
            <p class="lead">${kcSanitize(message.summary)?no_esc}</p>
            <#if traceId??>
                <p class="note" id="traceId">${msg("traceIdSupportMessage", traceId)}</p>
            </#if>
            <#if !skipLink?? && client?? && (client.baseUrl)?has_content>
                <a id="backToApplication" href="${client.baseUrl}">${msg("backToApplication")}</a>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
