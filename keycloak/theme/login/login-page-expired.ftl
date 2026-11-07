<#-- A sign-in step left open too long, or reached again with « Back »: go on where it stood, or
     start the sign-in again. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("pageExpiredTitle")}
    <#elseif section = "form">
        <p class="lead">${msg("sibylle.pageExpiredLead")}</p>
        <a id="loginContinueLink" class="button button-block" href="${url.loginAction}">${msg("sibylle.pageExpiredContinue")}</a>
        <a id="loginRestartLink" href="${url.loginRestartFlowUrl}">${msg("sibylle.pageExpiredRestart")}</a>
    </#if>
</@layout.registrationLayout>
