<#ftl output_format="plainText">
<#-- What the app asks of an account by e-mail (Keycloak's execute-actions-email). -->
<#assign requiredActionsText><#if requiredActions??><#list requiredActions as reqActionItem>${msg("requiredAction.${reqActionItem}")}<#sep>, </#list></#if></#assign>
<#if (user.firstName)?has_content>${msg("sibylle.hello", user.firstName)}<#else>${msg("sibylle.helloNoName")}</#if>

${msg("sibylle.actionsLead", requiredActionsText)}

${link}

${msg("sibylle.actionsNote", linkExpirationFormatter(linkExpiration))}

${msg("sibylle.signature")}
