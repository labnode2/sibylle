<#ftl output_format="plainText">
<#-- Confirme ton adresse: the app's own e-mail until specs/002-keycloak-auth. -->
<#if (user.firstName)?has_content>${msg("sibylle.hello", user.firstName)}<#else>${msg("sibylle.helloNoName")}</#if>

${msg("sibylle.verifyLead")}

${link}

${msg("sibylle.verifyNote", linkExpirationFormatter(linkExpiration))}

${msg("sibylle.signature")}
